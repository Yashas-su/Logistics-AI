package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:   1024,
	WriteBufferSize:  4096,
	HandshakeTimeout: 5 * time.Second,
	CheckOrigin:      func(r *http.Request) bool { return true },
}

// ── Client ────────────────────────────────────────────────────────────────

type SubscribeFilter struct {
	ShipmentIDs []string `json:"shipment_ids"`
	MinRisk     float64  `json:"min_risk"`
	EventTypes  []string `json:"event_types"`
}

type Client struct {
	conn     *websocket.Conn
	send     chan []byte
	tenantID string
	filters  SubscribeFilter
	mu       sync.Mutex
}

func (c *Client) matches(event *OutboundEvent) bool {
	if event.TenantID != "" && event.TenantID != c.tenantID {
		return false
	}
	if event.RiskScore > 0 && event.RiskScore < c.filters.MinRisk {
		return false
	}
	return true
}

func (c *Client) writePump(hub *Hub) {
	ticker := time.NewTicker(25 * time.Second)
	defer func() {
		ticker.Stop()
		hub.unregister <- c
		c.conn.Close()
	}()

	for {
		select {
		case message, ok := <-c.send:
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if !ok {
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}
			w, err := c.conn.NextWriter(websocket.TextMessage)
			if err != nil {
				return
			}
			w.Write(message)
			n := len(c.send)
			for i := 0; i < n; i++ {
				w.Write([]byte{'\n'})
				w.Write(<-c.send)
			}
			w.Close()
		case <-ticker.C:
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}

func (c *Client) readPump(hub *Hub) {
	defer func() {
		hub.unregister <- c
		c.conn.Close()
	}()
	c.conn.SetReadLimit(4096)
	c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
	c.conn.SetPongHandler(func(string) error {
		c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
		return nil
	})
	for {
		_, msg, err := c.conn.ReadMessage()
		if err != nil {
			return
		}
		var cmd struct {
			Action string          `json:"action"`
			Filter SubscribeFilter `json:"filter"`
		}
		if err := json.Unmarshal(msg, &cmd); err != nil {
			continue
		}
		switch cmd.Action {
		case "subscribe":
			c.mu.Lock()
			c.filters = cmd.Filter
			c.mu.Unlock()
		case "ping":
			c.send <- []byte(`{"type":"pong","ts":` + fmt.Sprintf("%d", time.Now().UnixMilli()) + `}`)
		}
	}
}

// ── Hub ───────────────────────────────────────────────────────────────────

type OutboundEvent struct {
	Type       string      `json:"type"`
	TenantID   string      `json:"tenant_id,omitempty"`
	ShipmentID string      `json:"shipment_id,omitempty"`
	RiskScore  float64     `json:"risk_score,omitempty"`
	Payload    interface{} `json:"payload"`
	Timestamp  int64       `json:"ts"`
}

type Hub struct {
	clients    map[*Client]struct{}
	broadcast  chan *OutboundEvent
	register   chan *Client
	unregister chan *Client
	mu         sync.RWMutex
}

func NewHub() *Hub {
	return &Hub{
		clients:    make(map[*Client]struct{}),
		broadcast:  make(chan *OutboundEvent, 4096),
		register:   make(chan *Client, 256),
		unregister: make(chan *Client, 256),
	}
}

func (h *Hub) Run() {
	for {
		select {
		case client := <-h.register:
			h.mu.Lock()
			h.clients[client] = struct{}{}
			h.mu.Unlock()
			slog.Info("client connected", "tenant", client.tenantID, "total", len(h.clients))

		case client := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.send)
			}
			h.mu.Unlock()

		case event := <-h.broadcast:
			data, err := json.Marshal(event)
			if err != nil {
				continue
			}
			h.mu.RLock()
			for client := range h.clients {
				if !client.matches(event) {
					continue
				}
				select {
				case client.send <- data:
				default:
					h.mu.RUnlock()
					h.mu.Lock()
					delete(h.clients, client)
					close(client.send)
					h.mu.Unlock()
					h.mu.RLock()
				}
			}
			h.mu.RUnlock()
		}
	}
}

// ── Demo broadcaster — polls Redis stream and fans out ────────────────────

func startDemoBroadcaster(ctx context.Context, hub *Hub) {
	slog.Info("Starting demo broadcaster (Redis stream poller)")
	go func() {
		ticker := time.NewTicker(3 * time.Second)
		defer ticker.Stop()
		shipmentIDs := []string{
			"SHP-8000", "SHP-8001", "SHP-8002", "SHP-8003", "SHP-8004",
			"SHP-8005", "SHP-8006", "SHP-8007", "SHP-8008", "SHP-8009",
		}
		i := 0
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				// Emit a synthetic position update
				sid := shipmentIDs[i%len(shipmentIDs)]
				i++
				risk := 0.05 + float64(i%20)*0.04
				hub.broadcast <- &OutboundEvent{
					Type:       "position_update",
					TenantID:   "demo-tenant",
					ShipmentID: sid,
					RiskScore:  risk,
					Payload: map[string]interface{}{
						"shipment_id": sid,
						"lat":         29.7 + float64(i%10)*0.1,
						"lon":         -95.4 + float64(i%8)*0.2,
						"risk_score":  risk,
						"status":      "on_track",
					},
					Timestamp: time.Now().UnixMilli(),
				}
			}
		}
	}()
}

// ── Auth ──────────────────────────────────────────────────────────────────

func validateJWT(authHeader string) (string, error) {
	secret := os.Getenv("JWT_SECRET")
	if secret == "" {
		secret = "dev-secret-change-in-production-use-256-bit-key"
	}
	if len(authHeader) < 8 {
		return "demo-tenant", nil
	}
	tokenStr := strings.TrimPrefix(authHeader, "Bearer ")
	token, err := jwt.Parse(tokenStr, func(t *jwt.Token) (interface{}, error) {
		if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method")
		}
		return []byte(secret), nil
	})
	if err != nil || !token.Valid {
		return "demo-tenant", nil
	}
	claims, ok := token.Claims.(jwt.MapClaims)
	if !ok {
		return "demo-tenant", nil
	}
	if tid, ok := claims["tid"].(string); ok {
		return tid, nil
	}
	return "demo-tenant", nil
}

// ── HTTP handlers ─────────────────────────────────────────────────────────

func (h *Hub) serveWS(w http.ResponseWriter, r *http.Request) {
	tenantID, _ := validateJWT(r.Header.Get("Authorization"))
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		slog.Error("upgrade failed", "err", err)
		return
	}
	client := &Client{
		conn:     conn,
		send:     make(chan []byte, 512),
		tenantID: tenantID,
		filters:  SubscribeFilter{MinRisk: 0},
	}
	// Send welcome
	welcome, _ := json.Marshal(map[string]interface{}{
		"type":      "connected",
		"tenant_id": tenantID,
		"ts":        time.Now().UnixMilli(),
	})
	client.send <- welcome

	h.register <- client
	go client.writePump(h)
	go client.readPump(h)
}

func (h *Hub) metricsHandler(w http.ResponseWriter, r *http.Request) {
	h.mu.RLock()
	count := len(h.clients)
	h.mu.RUnlock()
	fmt.Fprintf(w, "ws_connected_clients %d\nws_broadcast_queue_depth %d\n",
		count, len(h.broadcast))
}

// ── Reroute trigger endpoint (called by optimizer service) ────────────────

func (h *Hub) rerouteHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var payload struct {
		ShipmentID string   `json:"shipment_id"`
		NewRoute   []string `json:"new_route"`
		OldRoute   []string `json:"old_route"`
		RiskDelta  float64  `json:"risk_delta"`
		CostDelta  float64  `json:"cost_delta_usd"`
	}
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}
	h.broadcast <- &OutboundEvent{
		Type:       "reroute_decision",
		TenantID:   "demo-tenant",
		ShipmentID: payload.ShipmentID,
		Payload:    payload,
		Timestamp:  time.Now().UnixMilli(),
	}
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status":"broadcast_sent"}`))
}

// ── Main ──────────────────────────────────────────────────────────────────

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(logger)

	port := os.Getenv("WS_HUB_PORT")
	if port == "" {
		port = "8080"
	}

	ctx := context.Background()
	hub := NewHub()
	go hub.Run()
	startDemoBroadcaster(ctx, hub)

	mux := http.NewServeMux()
	mux.HandleFunc("/ws/shipments", hub.serveWS)
	mux.HandleFunc("/internal/reroute", hub.rerouteHandler)
	mux.HandleFunc("/metrics", hub.metricsHandler)
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		hub.mu.RLock()
		count := len(hub.clients)
		hub.mu.RUnlock()
		fmt.Fprintf(w, `{"status":"ok","connected_clients":%d}`, count)
	})

	srv := &http.Server{
		Addr:        ":" + port,
		Handler:     mux,
		ReadTimeout: 10 * time.Second,
		IdleTimeout: 120 * time.Second,
	}
	slog.Info("WebSocket hub listening", "port", port)
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		slog.Error("server error", "err", err)
		os.Exit(1)
	}
}
