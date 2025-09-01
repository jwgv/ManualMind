#!/bin/bash
# ManualMind MCP Client - Stdio Wrapper for HTTP Mode
# Bridges stdio JSON-RPC to HTTP calls

# Configuration
MCP_SERVER_HOST="${MCP_SERVER_HOST:-localhost}"
MCP_SERVER_PORT="${MCP_SERVER_PORT:-8001}"
MCP_BASE_URL="http://${MCP_SERVER_HOST}:${MCP_SERVER_PORT}"
API_KEY="${MANUALMIND_API_KEY:-}"

# Function to log errors (only to stderr)
log_error() {
    echo "MCP_CLIENT: $1" >&2
}

# Function to send single-line JSON response
send_json_response() {
    local response="$1"
    # Ensure it's on a single line and properly formatted
    echo "$response"
}

# Read JSON-RPC messages from stdin
while IFS= read -r line; do
    # Skip empty lines
    if [[ -z "$line" || "$line" == "{}" ]]; then
        continue
    fi

    log_error "Received: $line"

    # Parse JSON safely
    method=""
    id="null"
    params="{}"

    if command -v jq >/dev/null 2>&1; then
        method=$(echo "$line" | jq -r '.method // empty' 2>/dev/null || echo "")
        id=$(echo "$line" | jq -r '.id // null' 2>/dev/null || echo "null")
        params=$(echo "$line" | jq -c '.params // {}' 2>/dev/null || echo "{}")
    else
        log_error "jq not found - MCP server requires jq for JSON processing"
        continue
    fi

    log_error "Method: $method, ID: $id"

    case "$method" in
        "initialize")
            response='{"jsonrpc":"2.0","id":'$id',"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"manualmind","version":"0.1.0"}}}'
            send_json_response "$response"
            ;;

        "notifications/initialized")
            # Notifications don't get responses - just ignore silently
            log_error "Ignoring initialized notification"
            ;;

        "tools/list")
            log_error "Listing tools..."
            response='{"jsonrpc":"2.0","id":'$id',"result":{"tools":[{"name":"query_manuals","description":"Query the ManualMind system to search for information in user manuals using natural language","inputSchema":{"type":"object","properties":{"question":{"type":"string","description":"The question to ask about the manuals","minLength":1,"maxLength":500},"max_results":{"type":"integer","description":"Maximum number of results to return","minimum":1,"maximum":20,"default":5}},"required":["question"]}},{"name":"get_system_status","description":"Get the status of the ManualMind system including available documents and health","inputSchema":{"type":"object","properties":{},"additionalProperties":false}},{"name":"process_documents","description":"Trigger processing of documents in the ManualMind media folder","inputSchema":{"type":"object","properties":{},"additionalProperties":false}}]}}'
            send_json_response "$response"
            ;;

        "tools/call")
            log_error "Calling tool..."

            # Parse tool call parameters
            tool_name=$(echo "$params" | jq -r '.name // ""' 2>/dev/null || echo "")
            arguments=$(echo "$params" | jq -c '.arguments // {}' 2>/dev/null || echo "{}")

            log_error "Tool: $tool_name, Args: $arguments"

            if [[ -z "$tool_name" ]]; then
                response='{"jsonrpc":"2.0","id":'$id',"error":{"code":-32602,"message":"Missing tool name"}}'
            else
                case "$tool_name" in
                    "query_manuals")
                        question=$(echo "$arguments" | jq -r '.question // ""' 2>/dev/null || echo "")
                        max_results=$(echo "$arguments" | jq -r '.max_results // 5' 2>/dev/null || echo "5")

                        if [[ -z "$question" ]]; then
                            response='{"jsonrpc":"2.0","id":'$id',"result":{"content":[{"type":"text","text":"Question is required"}],"isError":true}}'
                        else
                            # Create HTTP payload
                            http_payload=$(jq -n --arg q "$question" --argjson mr "$max_results" '{"question": $q, "max_results": $mr}')

                            # Call the query endpoint
                            http_response=$(curl -s \
                                -H "Content-Type: application/json" \
                                -H "X-API-Key: $API_KEY" \
                                -X POST \
                                -d "$http_payload" \
                                "$MCP_BASE_URL/query" 2>/dev/null || echo '{"success":false,"error":"HTTP request failed"}')

                            log_error "Query response: $http_response"

                            # Check if this is from our HTTP MCP server or direct ManualMind API
                            success=$(echo "$http_response" | jq -r '.success // "unknown"' 2>/dev/null)

                            if [[ "$success" == "true" ]] || [[ "$success" == "false" ]]; then
                                # Response from HTTP MCP server
                                content=$(echo "$http_response" | jq -r '.content // "No response"' 2>/dev/null)
                                if [[ "$success" == "true" ]]; then
                                    escaped_content=$(echo "$content" | jq -Rs .)
                                    response='{"jsonrpc":"2.0","id":'$id',"result":{"content":[{"type":"text","text":'$escaped_content'}]}}'
                                else
                                    error_content=$(echo "$http_response" | jq -r '.error // "Unknown error"' 2>/dev/null)
                                    escaped_error=$(echo "$error_content" | jq -Rs .)
                                    response='{"jsonrpc":"2.0","id":'$id',"result":{"content":[{"type":"text","text":'$escaped_error'}],"isError":true}}'
                                fi
                            else
                                # Direct response from ManualMind API - check for query field
                                query_field=$(echo "$http_response" | jq -r '.query // empty' 2>/dev/null)
                                if [[ -n "$query_field" ]]; then
                                    # This looks like a direct ManualMind API response
                                    api_response=$(echo "$http_response" | jq -r '.response // "No response"' 2>/dev/null)
                                    escaped_response=$(echo "$api_response" | jq -Rs .)
                                    response='{"jsonrpc":"2.0","id":'$id',"result":{"content":[{"type":"text","text":'$escaped_response'}]}}'
                                else
                                    # Unknown response format
                                    fallback_content="Query completed but response format unrecognized"
                                    escaped_fallback=$(echo "$fallback_content" | jq -Rs .)
                                    response='{"jsonrpc":"2.0","id":'$id',"result":{"content":[{"type":"text","text":'$escaped_fallback'}]}}'
                                fi
                            fi
                        fi
                        ;;

                    "get_system_status")
                        http_response=$(curl -s -H "X-API-Key: $API_KEY" "$MCP_BASE_URL/status" 2>/dev/null || echo '{"success":false,"error":"HTTP request failed"}')

                        success=$(echo "$http_response" | jq -r '.success // "unknown"' 2>/dev/null)
                        if [[ "$success" == "true" ]]; then
                            content=$(echo "$http_response" | jq -r '.content // "Status retrieved"' 2>/dev/null)
                        else
                            # Try direct ManualMind API response format
                            status=$(echo "$http_response" | jq -r '.status // "unknown"' 2>/dev/null)
                            if [[ "$status" != "unknown" ]]; then
                                content="System Status: $status"
                            else
                                content="Status check completed"
                            fi
                        fi

                        escaped_content=$(echo "$content" | jq -Rs .)
                        response='{"jsonrpc":"2.0","id":'$id',"result":{"content":[{"type":"text","text":'$escaped_content'}]}}'
                        ;;

                    "process_documents")
                        http_response=$(curl -s \
                            -H "X-API-Key: $API_KEY" \
                            -X POST \
                            "$MCP_BASE_URL/process" 2>/dev/null || echo '{"success":false,"error":"HTTP request failed"}')

                        success=$(echo "$http_response" | jq -r '.success // "unknown"' 2>/dev/null)
                        if [[ "$success" == "true" ]]; then
                            content=$(echo "$http_response" | jq -r '.content // "Processing initiated"' 2>/dev/null)
                        else
                            content="Document processing initiated"
                        fi

                        escaped_content=$(echo "$content" | jq -Rs .)
                        response='{"jsonrpc":"2.0","id":'$id',"result":{"content":[{"type":"text","text":'$escaped_content'}]}}'
                        ;;

                    *)
                        escaped_tool_name=$(echo "$tool_name" | jq -Rs .)
                        response='{"jsonrpc":"2.0","id":'$id',"error":{"code":-32601,"message":"Unknown tool: '$tool_name'"}}'
                        ;;
                esac
            fi

            send_json_response "$response"
            ;;

        "prompts/list")
            # Return empty prompts list
            response='{"jsonrpc":"2.0","id":'$id',"result":{"prompts":[]}}'
            send_json_response "$response"
            ;;

        "resources/list")
            # Return empty resources list
            response='{"jsonrpc":"2.0","id":'$id',"result":{"resources":[]}}'
            send_json_response "$response"
            ;;

        "notifications/cancelled")
            # Ignore cancellation notifications
            log_error "Ignoring cancellation notification"
            ;;

        *)
            if [[ "$id" != "null" ]]; then
                response='{"jsonrpc":"2.0","id":'$id',"error":{"code":-32601,"message":"Method not found: '$method'"}}'
                send_json_response "$response"
            fi
            ;;
    esac
done