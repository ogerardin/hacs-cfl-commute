#!/bin/bash
#
# HA Docker setup with CFL Commute integration - IDEMPOTENT
# Can be run multiple times without destroying existing configuration
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
HA_CONFIG_DIR="$PROJECT_DIR/ha_config"
CONTAINER_NAME="ha-cfl-test"
HA_PORT=8123
HA_URL="http://localhost:$HA_PORT"
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="admin123"
TIMEZONE="Europe/Luxembourg"
LATITUDE=49.6116
LONGITUDE=6.1319

echo "========================================"
echo "=== HA Docker Setup (IDEMPOTENT) ==="
echo "========================================"

# Check if container exists and is running
CONTAINER_RUNNING=false
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    CONTAINER_RUNNING=true
    echo ""
    echo "[1/5] Container already running - using existing"
else
    # Container doesn't exist - create everything fresh
    echo ""
    echo "[1/5] Creating new container..."
    mkdir -p "$HA_CONFIG_DIR"
    mkdir -p "$HA_CONFIG_DIR/custom_components"
    
    # Only create config if it doesn't exist
    if [ ! -f "$HA_CONFIG_DIR/configuration.yaml" ]; then
        cat > "$HA_CONFIG_DIR/configuration.yaml" << EOF
homeassistant:
  name: Home
  latitude: $LATITUDE
  longitude: $LONGITUDE
  elevation: 0
  unit_system: metric
  time_zone: $TIMEZONE

http:
  server_port: $HA_PORT
EOF
    fi
    
    CUSTOM_COMPONENTS_DIR="$PROJECT_DIR/custom_components"
    
    docker run -d \
        --name "$CONTAINER_NAME" \
        -p "$HA_PORT:8123" \
        -v "$HA_CONFIG_DIR:/config" \
        -v "$CUSTOM_COMPONENTS_DIR:/config/custom_components" \
        --restart unless-stopped \
        homeassistant/home-assistant:stable
    
    echo "  Container started - waiting for HA..."
    sleep 60
fi

# Ensure config directory exists
mkdir -p "$HA_CONFIG_DIR"
mkdir -p "$HA_CONFIG_DIR/custom_components"

# Mount custom components (doesn't overwrite if already mounted)
CUSTOM_COMPONENTS_DIR="$PROJECT_DIR/custom_components"

# Wait for onboarding API
echo "[2/5] Checking HA status..."
MAX_WAIT=60
WAITED=0
while ! curl -s "$HA_URL/api/onboarding/users" > /dev/null 2>&1; do
    sleep 2
    WAITED=$((WAITED + 2))
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
        echo "  HA not ready, waiting longer..."
        sleep 20
        break
    fi
done

# Check if user already exists (has credentials)
echo "[3/5] Checking for existing user..."
USER_EXISTS=false
if docker exec "$CONTAINER_NAME" test -f /config/.storage/auth 2>/dev/null; then
    CREDS_COUNT=$(docker exec "$CONTAINER_NAME" cat /config/.storage/auth 2>/dev/null | grep -c '"username"' || echo "0")
    if [ "$CREDS_COUNT" -gt "0" ]; then
        USER_EXISTS=true
        echo "  User already exists - skipping creation"
    fi
fi

# Create user only if it doesn't exist
if [ "$USER_EXISTS" = false ]; then
    echo "[4/5] Creating admin user..."
    
    AUTH_RESPONSE=$(curl -s -X POST "$HA_URL/api/onboarding/users" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"Admin\",
            \"username\": \"$ADMIN_USERNAME\",
            \"password\": \"$ADMIN_PASSWORD\",
            \"client_id\": \"$HA_URL\",
            \"language\": \"en\"
        }")
    
    AUTH_CODE=$(echo "$AUTH_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('auth_code',''))" 2>/dev/null || echo "")
    
    if [ -n "$AUTH_CODE" ]; then
        TOKEN_RESPONSE=$(curl -s -X POST "$HA_URL/auth/token" \
            -H "Content-Type: application/x-www-form-urlencoded" \
            -d "grant_type=authorization_code&code=$AUTH_CODE&client_id=$HA_URL")
        
        ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")
        
        if [ -n "$ACCESS_TOKEN" ]; then
            curl -s -X POST "$HA_URL/api/onboarding/core_config" \
                -H "Content-Type: application/json" \
                -H "Authorization: Bearer $ACCESS_TOKEN" \
                -d "{
                    \"country\": \"LU\",
                    \"currency\": \"EUR\",
                    \"elev\": 0,
                    \"latitude\": $LATITUDE,
                    \"longitude\": $LONGITUDE,
                    \"time_zone\": \"$TIMEZONE\",
                    \"language\": \"en\"
                }" > /dev/null
            
            curl -s -X POST "$HA_URL/api/onboarding/analytics" \
                -H "Content-Type: application/json" \
                -H "Authorization: Bearer $ACCESS_TOKEN" \
                -d '{"analytics": false}' > /dev/null
            
            echo "  User created!"
        fi
    fi
else
    echo "[4/5] User already exists - skipping"
fi

# Mark onboarding complete if not already done
echo "[5/5] Checking onboarding status..."
ONBOARDING_DONE=false
if docker exec "$CONTAINER_NAME" cat /config/.storage/onboarding 2>/dev/null | grep -q "integration"; then
    ONBOARDING_DONE=true
fi

if [ "$ONBOARDING_DONE" = false ]; then
    docker exec "$CONTAINER_NAME" sh -c 'echo "{\"version\":4,\"minor_version\":1,\"key\":\"onboarding\",\"data\":{\"done\":[\"user\",\"core_config\",\"analytics\",\"integration\"]}}" > /config/.storage/onboarding' 2>/dev/null || true
    echo "  Onboarding marked complete"
    
    # Restart to apply
    docker restart "$CONTAINER_NAME" > /dev/null 2>&1 || true
    sleep 10
else
    echo "  Onboarding already complete"
fi

echo ""
echo "========================================"
echo "=== HA is ready! ==="
echo "========================================"
echo ""
echo "URL: http://localhost:8123"
echo ""
echo "If first time: Login with admin/admin123"
echo ""
echo "NEXT STEPS:"
echo "1. Settings → Devices & Services"
echo "2. Add Integration → CFL Commute"
echo ""
echo "Custom component mounted at:"
echo "  $CUSTOM_COMPONENTS_DIR/cfl_commute"
echo ""

open "$HA_URL" 2>/dev/null || echo "Open http://localhost:8123 manually"