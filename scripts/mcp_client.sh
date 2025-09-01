#!/bin/bash
# ManualMind MCP Client - Stdio Wrapper for HTTP Mode
# Bridges stdio JSON-RPC to HTTP calls

set -e

# Configuration
MCP_SERVER_HOST="${MCP_SERVER_HOST:-localhost}"
MCP_SERVER_PORT="${MCP_SERVER_PORT:-8001}"
MCP_BASE_URL="http://${MCP_SERVER_HOST}:${MCP_SERVER_PORT}"
API_KEY="${MANUALMIND_API_KEY:-}"

# Read JSON-RPC messages from stdin and proxy to HTTP server
while IFS= read -r line; do
    if [[ -z "$line" ]]; then
        continue
    fi

    # Parse JSON-RPC message
    method=$(echo "$line" | jq -r '.method // empty')
    params=$(echo "$line" | jq -r '.params // {}')
    id=$(echo "$line" | jq -r '.id // null')

    response=""

    case "$method" in
        "tools/list")
            # List tools
            http_response=$(curl -s -H "X-API-Key: $API_KEY" "$MCP_BASE_URL/tools")
            tools=$(echo "$http_response" | jq '.tools')
            response="{\"id\": $id, \"result\": {\"tools\": $tools}}"
            ;;

        "tools/call")
            # Call tool
            tool_name=$(echo "$params" | jq -r '.name')
            arguments=$(echo "$params" | jq -r '.arguments // {}')

            if [[ "$tool_name" == "query_manuals" ]]; then
                # Direct query endpoint
                question=$(echo "$arguments" | jq -r '.question')
                max_results=$(echo "$arguments" | jq -r '.max_results // 5')

                http_response=$(curl -s \
                    -H "Content-Type: application/json" \
                    -H "X-API-Key: $API_KEY" \
                    -X POST \
                    -d "{\"question\": \"$question\", \"max_results\": $max_results}" \
                    "$MCP_BASE_URL/query")
            else
                # Generic tool call
                http_response=$(curl -s \
                    -H "Content-Type: application/json" \
                    -H "X-API-Key: $API_KEY" \
                    -X POST \
                    -d "{\"name\": \"$tool_name\", \"arguments\": $arguments}" \
                    "$MCP_BASE_URL/call")
            fi

            # Convert HTTP response to MCP format
            success=$(echo "$http_response" | jq -r '.success // false')
            content=$(echo "$http_response" | jq -r '.content // ""')
            error=$(echo "$http_response" | jq -r '.error // null')

            if [[ "$success" == "true" ]]; then
                response="{\"id\": $id, \"result\": {\"content\": [{\"type\": \"text\", \"text\": \"$content\"}]}}"
            else
                response="{\"id\": $id, \"result\": {\"content\": [{\"type\": \"text\", \"text\": \"$error\"}], \"isError\": true}}"
            fi
            ;;

        *)
            # Unknown method
            response="{\"id\": $id, \"error\": {\"code\": -32601, \"message\": \"Method not found: $method\"}}"
            ;;
    esac

    # Send response to stdout
    echo "$response"
done