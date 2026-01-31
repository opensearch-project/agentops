#!/usr/bin/env bash
#
# AgentOps Installer
# Downloads and runs the interactive TUI installer
# Usage: curl -fsSL https://raw.githubusercontent.com/opensearch-project/agentops/main/install.sh | bash
#

set -e
set -o pipefail

# Configuration
REPO_URL="https://github.com/kylehounslow/agentops.git"
TEMP_DIR=$(mktemp -d)
INSTALL_METHOD="auto"
CURRENT_STEP=""  # Track current installation step

# Cleanup on exit
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo ""
        print_error "Installation failed"
        echo ""
        
        # Save logs if installation directory exists
        if [ -n "$INSTALL_DIR" ] && [ -d "$INSTALL_DIR" ]; then
            local log_file="$INSTALL_DIR/install-error.log"
            echo "Saving installation logs to: $log_file"
            
            {
                echo "=== AgentOps Installation Error Log ==="
                echo "Date: $(date)"
                echo "Installation Directory: $INSTALL_DIR"
                echo "Container Runtime: $CONTAINER_RUNTIME"
                echo "Failed Step: ${CURRENT_STEP:-Unknown}"
                echo ""
                echo "=== System Information ==="
                echo "OS: $(uname -s)"
                echo "Architecture: $(uname -m)"
                if command -v docker >/dev/null 2>&1; then
                    echo "Docker Version: $(docker --version 2>&1)"
                fi
                echo ""
                echo "=== Error Details ==="
                
                # Read error from temp file if it exists
                if [ -f "$TEMP_DIR/last_error.txt" ]; then
                    cat "$TEMP_DIR/last_error.txt"
                elif [ -f "$INSTALL_DIR/.install_error" ]; then
                    cat "$INSTALL_DIR/.install_error"
                else
                    echo "Step '$CURRENT_STEP' failed"
                    echo "No detailed error information captured"
                    echo ""
                    echo "Common issues:"
                    echo "  - Network connectivity problems"
                    echo "  - Docker not running or insufficient permissions"
                    echo "  - Insufficient disk space"
                    echo "  - Invalid configuration in docker-compose.yml"
                fi
                
                echo ""
                
                # Capture docker compose logs if services were started
                if [ -f "$INSTALL_DIR/docker-compose.yml" ]; then
                    echo "=== Docker Compose Logs ==="
                    cd "$INSTALL_DIR" 2>/dev/null
                    if [ "$CONTAINER_RUNTIME" = "docker" ]; then
                        docker compose logs 2>&1 || echo "No services running yet"
                    else
                        finch compose logs 2>&1 || echo "No services running yet"
                    fi
                fi
            } > "$log_file" 2>&1
            
            echo ""
            print_info "Troubleshooting:"
            echo "  1. Check logs: cat $log_file"
            echo "  2. Verify Docker is running: docker info"
            echo "  3. Check disk space: df -h"
            echo "  4. Visit: https://github.com/opensearch-project/agentops/issues"
        else
            print_info "For help, visit: https://github.com/opensearch-project/agentops/issues"
        fi
    fi
    
    # Clean up temp directory
    if [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
    fi
}

trap cleanup EXIT

# Handle interrupts gracefully
interrupt_handler() {
    echo ""
    echo "Installation interrupted by user"
    exit 130
}

trap interrupt_handler INT TERM

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --manual)
            INSTALL_METHOD="manual"
            shift
            ;;
        --tui)
            INSTALL_METHOD="tui"
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Colors and formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# Unicode symbols
CHECK="✓"
CROSS="✗"
ARROW="→"
STAR="★"

# Configuration
DEFAULT_INSTALL_DIR="agentops"

# Print functions
print_header() {
    echo -e "\n${CYAN}${BOLD}╔════════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${CYAN}${BOLD}║                                                            ║${RESET}"
    echo -e "${CYAN}${BOLD}║              🔭 AgentOps Installer v0.1                    ║${RESET}"
    echo -e "${CYAN}${BOLD}║                                                            ║${RESET}"
    echo -e "${CYAN}${BOLD}║            Open-source Agent Observability                 ║${RESET}"
    echo -e "${CYAN}${BOLD}║                                                            ║${RESET}"
    echo -e "${CYAN}${BOLD}╚════════════════════════════════════════════════════════════╝${RESET}\n"
}

print_step() {
    echo -e "${BLUE}${BOLD}${ARROW}${RESET} ${BOLD}$1${RESET}"
}

print_success() {
    echo -e "${GREEN}${CHECK}${RESET} $1"
}

print_error() {
    echo -e "${RED}${CROSS}${RESET} $1"
}

print_warning() {
    echo -e "${YELLOW}!${RESET} $1"
}

print_info() {
    echo -e "${DIM}  $1${RESET}"
}

# Progress bar function
show_progress() {
    local duration=$1
    local message=$2
    local width=50
    
    echo -ne "${message}"
    for ((i=0; i<=width; i++)); do
        sleep $(echo "scale=3; $duration/$width" | bc)
        local percent=$((i * 100 / width))
        local filled=$((i * 100 / width / 2))
        local empty=$((50 - filled))
        
        printf "\r${message} ["
        printf "%${filled}s" | tr ' ' '█'
        printf "%${empty}s" | tr ' ' '░'
        printf "] %3d%%" $percent
    done
    echo -e " ${GREEN}${CHECK}${RESET}"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Detect Docker or Finch
detect_container_runtime() {
    if command_exists docker && docker info >/dev/null 2>&1; then
        echo "docker"
    elif command_exists finch && finch info >/dev/null 2>&1; then
        echo "finch"
    else
        echo ""
    fi
}

# Check system requirements
check_requirements() {
    print_step "Checking system requirements..."
    
    local all_good=true
    
    # Check for git
    if command_exists git; then
        print_success "Git installed: $(git --version | head -n1)"
    else
        print_error "Git is not installed"
        print_info "Install git: https://git-scm.com/downloads"
        all_good=false
    fi
    
    # Check for container runtime
    CONTAINER_RUNTIME=$(detect_container_runtime)
    if [ -n "$CONTAINER_RUNTIME" ]; then
        print_success "Container runtime: $CONTAINER_RUNTIME"
        
        # Check Docker Compose
        if [ "$CONTAINER_RUNTIME" = "docker" ]; then
            if docker compose version >/dev/null 2>&1; then
                print_success "Docker Compose: $(docker compose version --short)"
            else
                print_error "Docker Compose is not available"
                print_info "Install Docker Compose: https://docs.docker.com/compose/install/"
                all_good=false
            fi
        elif [ "$CONTAINER_RUNTIME" = "finch" ]; then
            if finch compose version >/dev/null 2>&1; then
                print_success "Finch Compose: $(finch compose version --short)"
            else
                print_error "Finch Compose is not available"
                all_good=false
            fi
        fi
    else
        print_error "No container runtime found (Docker or Finch)"
        print_info "Install Docker: https://docs.docker.com/get-docker/"
        print_info "Or Finch (macOS): https://github.com/runfinch/finch"
        all_good=false
    fi
    
    # Check available memory
    if [[ "$OSTYPE" == "darwin"* ]]; then
        total_mem=$(sysctl -n hw.memsize | awk '{print int($1/1024/1024/1024)}')
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        total_mem=$(free -g | awk '/^Mem:/{print $2}')
    else
        total_mem=0
    fi
    
    if [ "$total_mem" -ge 4 ]; then
        print_success "Available memory: ${total_mem}GB"
    else
        print_warning "Low memory detected: ${total_mem}GB (4GB+ recommended)"
    fi
    
    echo ""
    
    if [ "$all_good" = false ]; then
        print_error "System requirements not met. Please install missing dependencies."
        exit 1
    fi
}

# Interactive configuration
configure_installation() {
    print_step "Configuration"
    echo ""
    
    # Installation directory
    echo -ne "${BOLD}Installation directory${RESET} ${DIM}(default: $DEFAULT_INSTALL_DIR)${RESET}: "
    read -r install_dir
    INSTALL_DIR="${install_dir:-$DEFAULT_INSTALL_DIR}"
    
    # Check if directory exists
    if [ -d "$INSTALL_DIR" ]; then
        echo -ne "${YELLOW}Directory exists. Overwrite?${RESET} ${DIM}(y/N)${RESET}: "
        read -r overwrite
        if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
            print_error "Installation cancelled"
            exit 0
        fi
        rm -rf "$INSTALL_DIR"
    fi
    
    # Include examples
    echo -ne "${BOLD}Include example services?${RESET} ${DIM}(weather-agent, travel-planner, canary)${RESET} ${DIM}(Y/n)${RESET}: "
    read -r include_examples
    INCLUDE_EXAMPLES="${include_examples:-Y}"
    
    # Include OTel Demo
    echo -ne "${BOLD}Include OpenTelemetry Demo?${RESET} ${DIM}(requires ~2GB additional memory)${RESET} ${DIM}(Y/n)${RESET}: "
    read -r include_otel_demo
    INCLUDE_OTEL_DEMO="${include_otel_demo:-Y}"
    
    # Custom credentials
    echo -ne "${BOLD}Customize OpenSearch credentials?${RESET} ${DIM}(y/N)${RESET}: "
    read -r custom_creds
    if [[ "$custom_creds" =~ ^[Yy]$ ]]; then
        echo -ne "${BOLD}OpenSearch username${RESET} ${DIM}(default: admin)${RESET}: "
        read -r opensearch_user
        OPENSEARCH_USER="${opensearch_user:-admin}"
        
        echo -ne "${BOLD}OpenSearch password${RESET} ${DIM}(default: My_password_123!@#)${RESET}: "
        read -rs opensearch_password
        echo ""
        OPENSEARCH_PASSWORD="${opensearch_password:-My_password_123!@#}"
    else
        OPENSEARCH_USER="admin"
        OPENSEARCH_PASSWORD="My_password_123!@#"
    fi
    
    echo ""
}

# Clone repository
clone_repository() {
    CURRENT_STEP="Cloning repository"
    print_step "Cloning AgentOps repository..."
    
    # Convert to absolute path
    if [[ "$INSTALL_DIR" != /* ]]; then
        INSTALL_DIR="$(pwd)/$INSTALL_DIR"
    fi
    
    if git clone --depth 1 "$REPO_URL" "$INSTALL_DIR" >/dev/null 2>&1; then
        print_success "Repository cloned to $INSTALL_DIR"
    else
        print_error "Failed to clone repository"
        exit 1
    fi
}

# Configure environment
configure_environment() {
    CURRENT_STEP="Configuring environment"
    print_step "Configuring environment..."
    
    # Verify we can access the directory
    if [ ! -d "$INSTALL_DIR" ]; then
        print_error "Installation directory not found: $INSTALL_DIR"
        exit 1
    fi
    
    # Verify .env file exists
    if [ ! -f "$INSTALL_DIR/.env" ]; then
        print_error ".env file not found in $INSTALL_DIR"
        exit 1
    fi
    
    cd "$INSTALL_DIR" || exit 1
    
    # Update .env file
    if [[ ! "$INCLUDE_EXAMPLES" =~ ^[Yy]$ ]]; then
        sed -i.bak 's/^INCLUDE_COMPOSE_EXAMPLES=/#INCLUDE_COMPOSE_EXAMPLES=/' .env
        print_info "Example services disabled"
    fi
    
    if [[ "$INCLUDE_OTEL_DEMO" =~ ^[Yy]$ ]]; then
        sed -i.bak 's/^#INCLUDE_COMPOSE_OTEL_DEMO=/INCLUDE_COMPOSE_OTEL_DEMO=/' .env
        print_info "OpenTelemetry Demo enabled"
    fi
    
    # Update credentials if customized
    if [ "$OPENSEARCH_USER" != "admin" ] || [ "$OPENSEARCH_PASSWORD" != "My_password_123!@#" ]; then
        sed -i.bak "s/^OPENSEARCH_USER=.*/OPENSEARCH_USER=$OPENSEARCH_USER/" .env
        sed -i.bak "s/^OPENSEARCH_PASSWORD=.*/OPENSEARCH_PASSWORD='$OPENSEARCH_PASSWORD'/" .env
        
        # Update Data Prepper configuration
        sed -i.bak "s/username: admin/username: $OPENSEARCH_USER/g" docker-compose/data-prepper/pipelines.yaml
        sed -i.bak "s/password: \"My_password_123!@#\"/password: \"$OPENSEARCH_PASSWORD\"/g" docker-compose/data-prepper/pipelines.yaml
        
        print_info "Credentials updated"
    fi
    
    # Clean up backup files
    find . -name "*.bak" -delete
    
    print_success "Environment configured"
}

# Pull Docker images
pull_images() {
    CURRENT_STEP="Building and pulling container images"
    print_step "Building and pulling container images..."
    echo ""
    
    cd "$INSTALL_DIR" || exit 1
    
    # First, build any custom images with progress indicator
    echo -ne "${DIM}Building custom OpenSearch image...${RESET}"
    
    # Spinner for build process
    local spinner=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
    local spinner_idx=0
    
    if [ "$CONTAINER_RUNTIME" = "docker" ]; then
        docker compose build >/dev/null 2>&1 &
    else
        finch compose build >/dev/null 2>&1 &
    fi
    
    local build_pid=$!
    
    # Show spinner while building
    while kill -0 $build_pid 2>/dev/null; do
        echo -ne "\r${DIM}Building custom OpenSearch image...${RESET} ${CYAN}${spinner[$spinner_idx]}${RESET}"
        spinner_idx=$(( (spinner_idx + 1) % ${#spinner[@]} ))
        sleep 0.1
    done
    
    wait $build_pid
    local build_exit=$?
    
    if [ $build_exit -eq 0 ]; then
        echo -e "\r${DIM}Building custom OpenSearch image...${RESET} ${GREEN}${CHECK}${RESET}"
    else
        echo -e "\r${DIM}Building custom OpenSearch image...${RESET} ${RED}${CROSS}${RESET}"
        
        # Capture build error
        local build_error
        if [ "$CONTAINER_RUNTIME" = "docker" ]; then
            build_error=$(docker compose build 2>&1)
        else
            build_error=$(finch compose build 2>&1)
        fi
        
        cat > "$INSTALL_DIR/.install_error" << EOF
Failed to build custom OpenSearch image

Build Error:
$build_error

This may be due to:
  - Network connectivity issues (can't pull base image)
  - Docker build permissions
  - Insufficient disk space
  - Invalid Dockerfile

Command that failed:
  $CONTAINER_RUNTIME compose build
EOF
        
        print_error "Failed to build custom OpenSearch image"
        echo ""
        print_info "Build error:"
        echo "$build_error" | head -20 | sed 's/^/  /'
        exit 1
    fi
    
    echo ""
    
    # Get list of images (excluding locally built ones)
    local images=()
    if [ "$CONTAINER_RUNTIME" = "docker" ]; then
        # Get all images from compose config, excluding those with 'build' directive
        images=($(docker compose config | grep 'image:' | awk '{print $2}' | grep -v '^agentops-' | sort -u))
    else
        images=($(finch compose config | grep 'image:' | awk '{print $2}' | grep -v '^agentops-' | sort -u))
    fi
    
    local total=${#images[@]}
    local current=0
    local pulled=0
    local skipped=0
    
    # Spinner characters
    local spinner=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
    
    for image in "${images[@]}"; do
        current=$((current + 1))
        
        # Calculate progress percentage
        local percent=$((current * 100 / total))
        local filled=$((percent / 5))
        local empty=$((20 - filled))
        
        # Pull with spinner
        if [ "$CONTAINER_RUNTIME" = "docker" ]; then
            docker pull "$image" >/dev/null 2>&1 &
        else
            finch pull "$image" >/dev/null 2>&1 &
        fi
        
        local pull_pid=$!
        
        # Show spinner while pulling
        local spinner_idx=0
        while kill -0 $pull_pid 2>/dev/null; do
            echo -ne "\r${DIM}[$current/$total]${RESET} ["
            printf "%${filled}s" | tr ' ' '█'
            printf "%${empty}s" | tr ' ' '░'
            echo -ne "] ${percent}% ${CYAN}${spinner[$spinner_idx]}${RESET} ${DIM}Pulling ${image}${RESET}"
            spinner_idx=$(( (spinner_idx + 1) % ${#spinner[@]} ))
            sleep 0.1
        done
        
        # Check if pull was successful
        wait $pull_pid
        local exit_code=$?
        
        # Clear line and show result
        echo -ne "\r${DIM}[$current/$total]${RESET} ["
        printf "%${filled}s" | tr ' ' '█'
        printf "%${empty}s" | tr ' ' '░'
        echo -ne "] ${percent}%"
        
        if [ $exit_code -eq 0 ]; then
            echo -e " ${GREEN}${CHECK}${RESET} ${DIM}${image}${RESET}"
            pulled=$((pulled + 1))
        else
            # Check if image exists locally
            if [ "$CONTAINER_RUNTIME" = "docker" ]; then
                if docker image inspect "$image" >/dev/null 2>&1; then
                    echo -e " ${YELLOW}⊘${RESET} ${DIM}${image} (cached)${RESET}"
                    skipped=$((skipped + 1))
                else
                    echo -e " ${RED}${CROSS}${RESET} ${DIM}${image} (failed)${RESET}"
                    
                    # Capture the actual error from docker
                    local docker_error
                    if [ "$CONTAINER_RUNTIME" = "docker" ]; then
                        docker_error=$(docker pull "$image" 2>&1)
                    else
                        docker_error=$(finch pull "$image" 2>&1)
                    fi
                    
                    # Write error immediately to install dir
                    cat > "$INSTALL_DIR/.install_error" << EOF
Failed to pull image: $image

Docker Error:
$docker_error

This may be due to:
  - Image doesn't exist in registry (check image name and tag)
  - Network connectivity issues
  - Docker Hub rate limiting
  - Image requires authentication

Command that failed:
  $CONTAINER_RUNTIME pull $image
EOF
                    
                    print_error "Failed to pull image: $image"
                    echo ""
                    print_info "Docker says:"
                    echo "$docker_error" | head -10 | sed 's/^/  /'
                    echo ""
                    print_info "This may be due to:"
                    echo "  - Image doesn't exist in registry (check image name and tag)"
                    echo "  - Network connectivity issues"
                    echo "  - Docker Hub rate limiting"
                    echo "  - Image requires authentication"
                    echo ""
                    print_info "Command that failed: $CONTAINER_RUNTIME pull $image"
                    exit 1
                fi
            else
                if finch image inspect "$image" >/dev/null 2>&1; then
                    echo -e " ${YELLOW}⊘${RESET} ${DIM}${image} (cached)${RESET}"
                    skipped=$((skipped + 1))
                else
                    echo -e " ${RED}${CROSS}${RESET} ${DIM}${image} (failed)${RESET}"
                    print_error "Failed to pull image: $image"
                    exit 1
                fi
            fi
        fi
    done
    
    echo ""
    print_success "Images ready: $pulled pulled, $skipped cached"
}

# Start services
start_services() {
    print_step "Starting AgentOps services..."
    echo ""
    
    cd "$INSTALL_DIR"
    
    if [ "$CONTAINER_RUNTIME" = "docker" ]; then
        docker compose up -d
    else
        finch compose up -d
    fi
    
    echo ""
    print_success "Services started"
}

# Wait for services
wait_for_services() {
    print_step "Waiting for services to be ready..."
    echo ""
    
    cd "$INSTALL_DIR"
    
    local max_wait=180
    local elapsed=0
    local check_interval=5
    
    # Check OpenSearch
    echo -ne "${DIM}Waiting for OpenSearch...${RESET}"
    while [ $elapsed -lt $max_wait ]; do
        if curl -s -k -u "$OPENSEARCH_USER:$OPENSEARCH_PASSWORD" "https://localhost:9200/_cluster/health" >/dev/null 2>&1; then
            echo -e " ${GREEN}${CHECK}${RESET}"
            break
        fi
        sleep $check_interval
        elapsed=$((elapsed + check_interval))
        echo -ne "."
    done
    
    if [ $elapsed -ge $max_wait ]; then
        echo -e " ${YELLOW}timeout${RESET}"
        print_warning "OpenSearch may still be starting. Check logs with: $CONTAINER_RUNTIME compose logs opensearch"
    fi
    
    # Check OpenSearch Dashboards
    echo -ne "${DIM}Waiting for OpenSearch Dashboards...${RESET}"
    elapsed=0
    while [ $elapsed -lt $max_wait ]; do
        if curl -s -f -u "$OPENSEARCH_USER:$OPENSEARCH_PASSWORD" "http://localhost:5601/api/status" >/dev/null 2>&1; then
            echo -e " ${GREEN}${CHECK}${RESET}"
            break
        fi
        sleep $check_interval
        elapsed=$((elapsed + check_interval))
        echo -ne "."
    done
    
    if [ $elapsed -ge $max_wait ]; then
        echo -e " ${YELLOW}timeout${RESET}"
        print_warning "Dashboards may still be starting. Check logs with: $CONTAINER_RUNTIME compose logs opensearch-dashboards"
    fi
    
    echo ""
    print_success "Services are ready"
}

# Print summary
print_summary() {
    echo ""
    echo -e "${GREEN}${BOLD}╔════════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${GREEN}${BOLD}║                                                            ║${RESET}"
    echo -e "${GREEN}${BOLD}║              ${STAR} Installation Complete! ${STAR}                    ║${RESET}"
    echo -e "${GREEN}${BOLD}║                                                            ║${RESET}"
    echo -e "${GREEN}${BOLD}╚════════════════════════════════════════════════════════════╝${RESET}"
    echo ""
    
    echo -e "${BOLD}Access Points:${RESET}"
    echo -e "  ${CYAN}${ARROW}${RESET} OpenSearch Dashboards: ${BOLD}http://localhost:5601${RESET}"
    echo -e "  ${CYAN}${ARROW}${RESET} Prometheus:            ${BOLD}http://localhost:9090${RESET}"
    echo -e "  ${CYAN}${ARROW}${RESET} OpenSearch API:        ${BOLD}https://localhost:9200${RESET}"
    
    if [[ "$INCLUDE_EXAMPLES" =~ ^[Yy]$ ]]; then
        echo -e "  ${CYAN}${ARROW}${RESET} Weather Agent:        ${BOLD}http://localhost:8000${RESET}"
        echo -e "  ${CYAN}${ARROW}${RESET} Travel Planner:       ${BOLD}http://localhost:8003${RESET}"
    fi
    
    if [[ "$INCLUDE_OTEL_DEMO" =~ ^[Yy]$ ]]; then
        echo -e "  ${CYAN}${ARROW}${RESET} OTel Demo Frontend:   ${BOLD}http://localhost:8080${RESET}"
        echo -e "  ${CYAN}${ARROW}${RESET} Load Generator:       ${BOLD}http://localhost:8089${RESET}"
    fi
    
    echo ""
    echo -e "${BOLD}Credentials:${RESET}"
    echo -e "  ${CYAN}${ARROW}${RESET} Username: ${BOLD}$OPENSEARCH_USER${RESET}"
    echo -e "  ${CYAN}${ARROW}${RESET} Password: ${BOLD}$OPENSEARCH_PASSWORD${RESET}"
    
    echo ""
    echo -e "${BOLD}Useful Commands:${RESET}"
    echo -e "  ${DIM}# View logs${RESET}"
    echo -e "  ${BOLD}cd $INSTALL_DIR && $CONTAINER_RUNTIME compose logs -f${RESET}"
    echo ""
    echo -e "  ${DIM}# Stop services${RESET}"
    echo -e "  ${BOLD}cd $INSTALL_DIR && $CONTAINER_RUNTIME compose down${RESET}"
    echo ""
    echo -e "  ${DIM}# Stop and remove data${RESET}"
    echo -e "  ${BOLD}cd $INSTALL_DIR && $CONTAINER_RUNTIME compose down -v${RESET}"
    
    echo ""
    echo -e "${BOLD}Next Steps:${RESET}"
    echo -e "  1. Visit ${CYAN}http://localhost:5601${RESET} to explore your data"
    echo -e "  2. Check out ${CYAN}$INSTALL_DIR/examples/${RESET} for instrumentation examples"
    echo -e "  3. Read ${CYAN}$INSTALL_DIR/README.md${RESET} for detailed documentation"
    
    echo ""
    echo -e "${DIM}For support, visit: https://github.com/opensearch-project/agentops${RESET}"
    echo ""
}

# Main installation flow
main() {
    print_header
    
    # For now, always use manual installation since TUI installer is in development
    # TODO: Enable TUI installer once it's merged to main branch
    INSTALL_METHOD="manual"
    
    # Check if Node.js is available for TUI (future use)
    # if [ "$INSTALL_METHOD" = "auto" ]; then
    #     if command_exists node && command_exists npm; then
    #         INSTALL_METHOD="tui"
    #     else
    #         INSTALL_METHOD="manual"
    #     fi
    # fi
    
    if [ "$INSTALL_METHOD" = "tui" ]; then
        echo -e "${CYAN}${BOLD}Starting TUI installer...${RESET}\n"
        run_tui_installer
    else
        echo -e "${CYAN}${BOLD}Starting installation...${RESET}\n"
        run_manual_installer
    fi
}

# Run TUI installer
run_tui_installer() {
    print_step "Downloading TUI installer..."
    
    if ! git clone --depth 1 "$REPO_URL" "$TEMP_DIR/agentops" >/dev/null 2>&1; then
        print_error "Failed to clone repository"
        exit 1
    fi
    
    # Check if installer directory exists
    if [ ! -d "$TEMP_DIR/agentops/installer" ]; then
        print_warning "TUI installer not available yet, falling back to manual installation"
        echo ""
        INSTALL_METHOD="manual"
        run_manual_installer
        return
    fi
    
    print_step "Installing dependencies..."
    if ! (cd "$TEMP_DIR/agentops/installer" && npm install --silent >/dev/null 2>&1); then
        print_error "Failed to install dependencies"
        print_warning "Falling back to manual installation"
        echo ""
        INSTALL_METHOD="manual"
        run_manual_installer
        return
    fi
    
    print_step "Launching TUI..."
    cd "$TEMP_DIR/agentops/installer" && npm run dev
}

# Run manual installer (original bash script logic)
run_manual_installer() {
    check_requirements
    configure_installation
    clone_repository
    configure_environment
    pull_images
    start_services
    wait_for_services
    print_summary
}

# Run main function
main
