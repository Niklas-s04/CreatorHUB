#!/bin/bash

# validate-secrets.sh - Pre-deploy secret validation
# Ensures all required secrets meet minimum security requirements

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# Load .env if it exists
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

echo "=========================================="
echo "Pre-Deploy Secret Validation"
echo "=========================================="

# Helper function for validation checks
check_secret() {
    local var_name=$1
    local min_length=$2
    local description=$3
    
    local var_value="${!var_name:-}"
    
    if [ -z "$var_value" ]; then
        echo -e "${RED}✗ ERROR${NC}: ${var_name} is not set"
        echo "  Description: ${description}"
        ((ERRORS++))
        return 1
    fi
    
    local actual_length=${#var_value}
    if [ "$actual_length" -lt "$min_length" ]; then
        echo -e "${RED}✗ ERROR${NC}: ${var_name} is too short (${actual_length}/${min_length} chars)"
        echo "  Description: ${description}"
        ((ERRORS++))
        return 1
    fi
    
    echo -e "${GREEN}✓ PASS${NC}: ${var_name} (${actual_length} chars)"
    return 0
}

# Check forbidden patterns
check_not_placeholder() {
    local var_name=$1
    local forbidden_value=$2
    local description=$3
    
    local var_value="${!var_name:-}"
    
    if [ "$var_value" = "$forbidden_value" ]; then
        echo -e "${RED}✗ ERROR${NC}: ${var_name} still has placeholder value: '${var_value}'"
        echo "  Description: ${description}"
        ((ERRORS++))
        return 1
    fi
}

# ========== Validation Rules ==========

echo ""
echo "Checking required secrets..."

check_secret "JWT_SECRET" 32 "JWT signing key must be at least 32 characters"
check_secret "POSTGRES_PASSWORD" 1 "Database password must be set"
check_secret "BOOTSTRAP_ADMIN_PASSWORD" 12 "Admin password must be at least 12 characters"

echo ""
echo "Checking for placeholder values..."

check_not_placeholder "JWT_SECRET" "change_me" "JWT_SECRET must not be placeholder value"
check_not_placeholder "BOOTSTRAP_ADMIN_PASSWORD" "admin" "BOOTSTRAP_ADMIN_PASSWORD must not use default value"

echo ""
echo "Checking database configuration..."

if [ -z "${DATABASE_URL:-}" ]; then
    # DATABASE_URL can be auto-constructed from POSTGRES_* vars
    if [ -z "${POSTGRES_USER:-}" ] || [ -z "${POSTGRES_DB:-}" ]; then
        echo -e "${YELLOW}⚠ WARNING${NC}: Neither DATABASE_URL nor POSTGRES_USER/POSTGRES_DB fully set"
    else
        echo -e "${GREEN}✓ PASS${NC}: POSTGRES_* variables set for auto-construction"
    fi
else
    echo -e "${GREEN}✓ PASS${NC}: DATABASE_URL is configured"
fi

# ========== Summary ==========

echo ""
echo "=========================================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All validations passed!${NC}"
    echo "=========================================="
    exit 0
else
    echo -e "${RED}✗ ${ERRORS} validation error(s) found${NC}"
    echo "=========================================="
    exit 1
fi
