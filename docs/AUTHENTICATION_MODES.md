# Authentication Modes Reference

Server Lux supports three authentication modes that can be switched easily via environment configuration.

## Mode Comparison

| Feature | Community Edition | Token Auth | Auth0 |
|---------|------------------|------------|--------|
| **Authentication** | None | Bearer Token | OAuth 2.0 JWT |
| **Setup Time** | 30 seconds | 2 minutes | 15 minutes |
| **Use Case** | Local dev | Simple deploy | Production |
| **Security Level** | ⚠️ None | ⭐⭐ Basic | ⭐⭐⭐ Enterprise |
| **Configuration Lines** | 1 | 2 | 4 |
| **External Dependencies** | None | None | Auth0 Service |
| **Token Rotation** | N/A | Manual | Automatic |
| **User Management** | N/A | Manual | Auth0 Dashboard |
| **Cost** | Free | Free | Auth0 Pricing |
| **Recommended For** | Development | Internal APIs | Public APIs |

---

## Mode 1: Community Edition (AUTH_TYPE=none)

### Configuration
```bash
AUTH_TYPE=none
```

### Features
- ✅ No authentication required
- ✅ Instant setup (30 seconds)
- ✅ Perfect for local development
- ✅ Full API access
- ✅ No tokens to manage
- ⚠️ **Not for production**

### When to Use
- Local development
- Testing and learning
- Personal projects on localhost
- CI/CD testing
- Development environments

### Example
```bash
# No auth header needed
curl http://localhost:8080/api/v1/status
```

### Quick Start
```bash
cp .env.community .env
python src/main.py
```

📖 **Full Guide:** [COMMUNITY_EDITION.md](COMMUNITY_EDITION.md)

---

## Mode 2: Token Authentication (AUTH_TYPE=token)

### Configuration
```bash
AUTH_TYPE=token
API_TOKEN=your_secure_random_token_here
```

### Features
- ✅ Simple bearer token authentication
- ✅ Easy to implement
- ✅ No external dependencies
- ✅ Good for internal APIs
- ⚠️ Manual token management
- ⚠️ Single shared token

### When to Use
- Internal tools and services
- Simple deployments
- Microservices communication
- When Auth0 is overkill
- Budget-conscious projects

### Example
```bash
curl http://localhost:8080/api/v1/status \
  -H "Authorization: Bearer your_secure_random_token_here"
```

### Generating Secure Tokens
```bash
# Using Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Using OpenSSL
openssl rand -base64 32

# Using Node.js
node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"
```

### Security Considerations
- Use long, random tokens (32+ bytes)
- Rotate tokens regularly
- Store tokens securely (use environment variables)
- Use HTTPS in production
- Consider Auth0 for better security

📖 **Full Guide:** [AUTH_README.md](AUTH_README.md)

---

## Mode 3: Auth0 Authentication (AUTH_TYPE=auth0)

### Configuration
```bash
AUTH_TYPE=auth0
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_AUDIENCE=https://api.yourdomain.com
AUTH0_ALGORITHMS=RS256
```

### Features
- ✅ OAuth 2.0 / OpenID Connect
- ✅ JWT token validation
- ✅ Automatic token rotation
- ✅ User management dashboard
- ✅ Social login support
- ✅ Multi-factor authentication
- ✅ Token revocation
- ✅ Audit logs
- ⭐ **Recommended for production**

### When to Use
- Public-facing APIs
- Production deployments
- Enterprise applications
- When user management is needed
- Multi-tenant applications
- When compliance is required

### Example
```bash
# First, get a token from Auth0
TOKEN=$(curl --request POST \
  --url 'https://your-tenant.auth0.com/oauth/token' \
  --header 'content-type: application/json' \
  --data '{
    "client_id":"YOUR_CLIENT_ID",
    "client_secret":"YOUR_CLIENT_SECRET",
    "audience":"https://api.yourdomain.com",
    "grant_type":"client_credentials"
  }' | jq -r '.access_token')

# Then use the token
curl http://localhost:8080/api/v1/status \
  -H "Authorization: Bearer $TOKEN"
```

### Setup Steps
1. Create Auth0 account
2. Create API in Auth0 dashboard
3. Create application (Machine to Machine)
4. Configure environment variables
5. Test authentication

### Security Features
- RS256 signature verification
- Token expiration checking
- Audience validation
- Issuer validation
- JWKS caching
- Automatic key rotation

📖 **Full Guide:** [AUTH0_SETUP.md](AUTH0_SETUP.md)

---

## Switching Between Modes

### Zero Code Changes Required

Simply update your `.env` file and restart the server:

```bash
# Switch to Community Edition
echo "AUTH_TYPE=none" > .env

# Switch to Token Auth
echo "AUTH_TYPE=token" > .env
echo "API_TOKEN=$(openssl rand -base64 32)" >> .env

# Switch to Auth0
echo "AUTH_TYPE=auth0" > .env
echo "AUTH0_DOMAIN=your-tenant.auth0.com" >> .env
echo "AUTH0_AUDIENCE=https://api.yourdomain.com" >> .env

# Restart server
python src/main.py
```

### Confirmation

The server logs the active authentication mode on startup:

```
Authentication Type: none (Community Edition - No authentication required ✨)
```
or
```
Authentication Type: token (Token-based authentication enabled)
```
or
```
Authentication Type: auth0 (Auth0 JWT authentication enabled)
```

---

## Architecture

All three modes use the same underlying architecture with the **Strategy Pattern**:

```
Request
  ↓
Authenticator (unified interface)
  ↓
AuthConfig (reads AUTH_TYPE from environment)
  ↓
AuthenticationStrategyFactory
  ↓
┌─────────────┬──────────────┬─────────────────┐
│             │              │                 │
NoAuthStrategy TokenStrategy Auth0Strategy
│             │              │                 │
Always valid  Bearer token   JWT validation
             validation      with Auth0 JWKS
  ↓             ↓              ↓
Protected Endpoint Executes
```

### Benefits of This Architecture
- ✅ **Single codebase** for all auth methods
- ✅ **No if-else chains** (Strategy pattern)
- ✅ **Easy to extend** with new methods
- ✅ **Type-safe** with full type hints
- ✅ **Testable** with clear interfaces
- ✅ **Follows SOLID principles**

---

## Environment Variables Reference

### Common
- `AUTH_TYPE` - Authentication mode: `none`, `token`, or `auth0`
- `PORT` - Server port (default: 8080)
- `DEPLOYMENT_MODE` - Deployment mode: `local` or `production`

### Token Mode
- `API_TOKEN` - Bearer token for authentication

### Auth0 Mode
- `AUTH0_DOMAIN` - Auth0 tenant domain (e.g., your-tenant.auth0.com)
- `AUTH0_AUDIENCE` - API identifier (e.g., https://api.yourdomain.com)
- `AUTH0_ALGORITHMS` - Signing algorithms (default: RS256)

---

## Error Responses

### Community Mode (No Auth)
No authentication errors - all requests are allowed.

### Token Mode
```json
{
  "status": "error",
  "error": "Missing Authorization header",
  "error_type": "missing_authorization"
}
```

```json
{
  "status": "error",
  "error": "Invalid authentication token",
  "error_type": "invalid_token"
}
```

### Auth0 Mode
```json
{
  "status": "error",
  "error": "Invalid JWT token",
  "error_type": "invalid_jwt"
}
```

```json
{
  "status": "error",
  "error": "JWT token has expired",
  "error_type": "expired_jwt"
}
```

---

## Swagger UI Integration

The Swagger documentation at `/docs/` automatically adapts:

| Mode | Swagger Behavior |
|------|------------------|
| Community | No "Authorize" button needed |
| Token | Shows "Bearer" authentication input |
| Auth0 | Shows "Auth0" JWT authentication input |

---

## Performance Comparison

| Mode | Validation Time | Overhead |
|------|----------------|----------|
| Community | 0ms (no validation) | None |
| Token | <1ms (string comparison) | Minimal |
| Auth0 | 1-2ms (JWT verify, cached JWKS) | Low |

All modes are production-ready in terms of performance.

---

## Migration Paths

### Development → Production

```
Community Edition (none)
        ↓
Token Authentication (simple production)
        ↓
Auth0 Authentication (enterprise production)
```

### Recommended Path
1. **Start:** Community Edition for development
2. **Internal:** Token Auth for internal services
3. **Production:** Auth0 for public APIs

---

## Best Practices by Mode

### Community Edition
- ✅ Use only on localhost
- ✅ Never expose to internet
- ✅ Perfect for learning and testing
- ⚠️ Disable in production

### Token Authentication
- ✅ Use long, random tokens (32+ bytes)
- ✅ Store in environment variables
- ✅ Rotate regularly
- ✅ Use HTTPS
- ⚠️ Consider Auth0 for public APIs

### Auth0 Authentication
- ✅ Enable MFA in Auth0 dashboard
- ✅ Configure proper audience
- ✅ Use attack protection features
- ✅ Monitor Auth0 logs
- ✅ Set up anomaly detection

---

## FAQ

**Q: Which mode should I use for my project?**
- **Local development:** Community Edition
- **Internal tools:** Token Authentication
- **Production API:** Auth0

**Q: Can I use different modes in different environments?**
Yes! Use Community in dev, Token in staging, Auth0 in production.

**Q: Do I need to change my code when switching modes?**
No! Just update `.env` and restart the server.

**Q: Is Community Edition production-ready?**
Technically yes, but **never use it in production**. It has no security.

**Q: How much does Auth0 cost?**
Auth0 has a free tier (7,000 active users). Check [Auth0 pricing](https://auth0.com/pricing).

---

## Resources

- 📖 [QUICK_START.md](QUICK_START.md) - Get started in 30 seconds
- 🎉 [COMMUNITY_EDITION.md](COMMUNITY_EDITION.md) - Community Edition guide
- 🔑 [AUTH0_SETUP.md](AUTH0_SETUP.md) - Complete Auth0 setup
- 📚 [AUTH_README.md](AUTH_README.md) - Authentication overview
- 🧪 [tests/test_auth.py](tests/test_auth.py) - Authentication tests
- 🌐 Swagger UI: `http://localhost:8080/docs/`

---

**Choose the mode that fits your needs and switch anytime!** 🚀
