# 🌟 Options Analysis Platform — Full-Stack Web App (Flask + Multi-Model Pricing)

> Production-grade web application for options analysis, multi-model pricing, Greeks, portfolio management, statistical analysis, and global macro dashboard. Built with Flask, bcrypt authentication, modular architecture, and real-time data integration.

---

## 🇬🇧 English

### Overview

A complete **options analytics platform** served as a web application. Designed for traders and analysts who need institutional-grade pricing tools accessible from a browser — with authentication, user management, and subscription tiers.

This is not a script. It is a full-stack application with a modular backend, REST API, persistent sessions, structured logging, automated backups, and a chatbot layer.

### Architecture

```
Flask App (app_clean.py)
│
├── core/
│   ├── pricing.py          ← Multi-model option pricer (BS, Binomial, Black-76)
│   ├── portfolio.py        ← Portfolio of option positions
│   ├── strategies.py       ← Strategy builder (spreads, straddles, etc.)
│   ├── database.py         ← User & session persistence
│   ├── subscription.py     ← Subscription plan management
│   ├── security.py         ← bcrypt hashing, CSRF, rate limiting
│   ├── chatbot.py          ← Integrated trading chatbot
│   ├── logger.py           ← Structured rotating log system
│   └── backup.py           ← Automated DB backup with compression
│
├── opciones_comparador.py  ← BS, Binomial, Black-76 pricing engines
├── analisis_griegas.py     ← Full Greeks + scenario analysis
├── trading_statistical_analysis.py ← Historical vol, expected move, lognormal
│
├── templates/              ← Jinja2 HTML templates
└── static/                 ← CSS/JS assets
```

### Pricing models

| Model | Use case |
|---|---|
| **Black-Scholes (advanced)** | European options on spot |
| **Black-76** | European options on futures |
| **Binomial tree** | American options (early exercise) |

All models support:
- Implied volatility inversion (numerical)
- Full Greeks: Δ, Γ, ν, Θ, ρ
- Market vs theoretical comparison (mispricing)

### Features by module

**Options pricing**
- Multi-model pricing with IV inversion
- Greeks calculation and scenario analysis
- Market price vs theoretical mispricing detection

**Portfolio management**
- Multi-position portfolio builder
- Strategy templates: straddles, strangles, spreads, condors
- Portfolio-level Greeks aggregation

**Statistical analysis**
- Historical volatility from market data (`yfinance`)
- Expected move calculation (1σ, 2σ ranges)
- Lognormal return distribution
- Implied probability distribution from option chain

**Global macro dashboard**
- World map with interest rates, inflation, GDP by country
- 20+ countries including G10 and EM
- Color-scaled choropleth visualization

**Authentication & security**
- `bcrypt` password hashing
- Persistent server-side sessions (Flask-Session)
- Rate limiting per endpoint and per user
- CSRF protection
- Production/development mode separation
- `SECRET_KEY` enforcement in production

**Infrastructure**
- Rotating file logs (general + auth + error streams)
- Automated database backup on startup (production mode)
- Backup compression and cleanup (7-day retention)
- Modular import with graceful fallback on missing modules
- Colab / local / server environment detection

### REST API endpoints (sample)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/price` | Price option with selected model |
| `POST` | `/api/greeks` | Calculate full Greeks |
| `POST` | `/api/iv` | Extract implied volatility |
| `POST` | `/api/portfolio` | Analyze option portfolio |
| `POST` | `/api/stats` | Historical vol + expected move |
| `POST` | `/api/macro/map` | Global macro indicator map |
| `POST` | `/api/chat` | Chatbot query |
| `GET`  | `/login` | Auth page |
| `GET`  | `/dashboard` | Main trading dashboard |

### Requirements

```bash
pip install flask flask-session bcrypt python-dotenv numpy scipy pandas yfinance
```

### Configuration (`.env`)

```
SECRET_KEY=your-secure-secret-key
FLASK_ENV=production          # or development
ALLOWED_ORIGINS=yourdomain.com
```

### Running

```bash
python app_clean.py
# → http://localhost:5000/login
```

Default users (change before deploying):
```
admin / admin123
trader / trader123
analyst / analyst123
```

### Skills demonstrated

- Full-stack Flask application with modular architecture
- Multi-model options pricing: Black-Scholes, Black-76, Binomial
- Implied volatility inversion (numerical methods)
- Greeks calculation and portfolio-level aggregation
- Historical volatility and statistical distribution analysis
- bcrypt authentication with rate limiting and CSRF protection
- Server-side persistent sessions (Flask-Session)
- REST API design with structured JSON responses
- Automated backup system with compression and retention policy
- Structured rotating logs (general / auth / error streams)
- Global macro data layer with choropleth map visualization
- Integrated chatbot module
- Environment-aware configuration (dev / prod separation)
- Graceful module degradation (missing deps don't crash the app)

---

## 🇦🇷 Español

### Resumen

Plataforma web completa de análisis de opciones. Diseñada para traders y analistas que necesitan herramientas de pricing institucional accesibles desde un navegador — con autenticación, gestión de usuarios y niveles de suscripción.

No es un script. Es una aplicación full-stack con backend modular, API REST, sesiones persistentes, logging estructurado, backups automáticos y chatbot integrado.

### Modelos de pricing

| Modelo | Uso |
|---|---|
| **Black-Scholes (avanzado)** | Opciones europeas sobre spot |
| **Black-76** | Opciones europeas sobre futuros |
| **Árbol binomial** | Opciones americanas (ejercicio anticipado) |

### Módulos principales

- **Pricing:** multi-modelo con inversión numérica de IV y Greeks completos
- **Portfolio:** constructor de posiciones con estrategias predefinidas (straddle, spread, cóndor)
- **Estadístico:** volatilidad histórica, expected move, distribución lognormal, probabilidades implícitas
- **Macro:** mapa mundial de tasas, inflación y GDP con escala de colores
- **Seguridad:** bcrypt, sesiones persistentes, rate limiting, CSRF, modo producción/desarrollo
- **Infraestructura:** logs rotativos, backup automático al inicio, limpieza de sesiones expiradas

### Skills que demuestra

- Aplicación Flask full-stack con arquitectura modular
- Pricing multi-modelo: Black-Scholes, Black-76, Binomial
- Inversión de volatilidad implícita (métodos numéricos)
- Cálculo de Greeks y agregación a nivel portfolio
- Análisis de volatilidad histórica y distribución estadística
- Autenticación bcrypt con rate limiting y CSRF
- Sesiones persistentes del lado del servidor (Flask-Session)
- Diseño de API REST con respuestas JSON estructuradas
- Sistema de backup automático con compresión y retención
- Logs rotativos estructurados (general / auth / error)
- Capa de datos macro global con visualización choropleth
- Módulo chatbot integrado
- Configuración sensible al entorno (dev / prod)
- Degradación graceful por módulos faltantes

---

## Author

**unabomber1618** · [github.com/unabomber1618](https://github.com/unabomber1618)

> *Full-stack options analytics platform — multi-model pricing, portfolio management, statistical analysis, and global macro dashboard. Production-grade Flask application.*
