# What2Wear Project: Complete Capabilities & Technology Stack

**Version:** 5.0  
**Last Updated:** September 13, 2025  
**Status:** Production Ready

---

## 🎯 Project Overview

What2Wear is a sophisticated wardrobe management and outfit suggestion application that combines intelligent color analysis, rule-based matching algorithms, and modern web technologies to help users discover perfect clothing combinations from their personal wardrobe.

### Core Mission
Help users quickly pair items in their wardrobe by suggesting **top↔bottom** matches using **color harmony + semantic tags**, with secure image storage and explainable recommendations.

---

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │    Backend      │    │   Supabase      │
│   (Next.js)     │◄──►│   (FastAPI)     │◄──►│ (Auth/DB/Store) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Data Flow:**
- Users authenticate via Supabase Auth
- Images are compressed client-side and uploaded to private Supabase Storage
- FastAPI handles color extraction, analysis, and suggestion generation
- PostgreSQL with RLS provides secure, per-user data isolation
- Real-time suggestions powered by rule-based algorithms

---

## 🔧 Core Modules & Communication Architecture

### **1. Authentication & Security Layer**

**Module:** `deps.py` (Backend) + `auth.ts` (Frontend)

```
[Frontend] ──JWT Token──► [Backend] ──Validation──► [Supabase Auth]
    │                         │                           │
    └─Session Management      └─User ID Extraction        └─User Verification
```

**Communication Flow:**
1. **Frontend**: Supabase client handles login/signup
2. **Token Flow**: JWT tokens passed via `Authorization: Bearer <token>` headers
3. **Backend Validation**: `get_user_id()` function validates tokens with Supabase
4. **User Context**: Extracted user ID used for RLS and data isolation

**Key Functions:**
- `get_user_id()`: JWT token validation and user extraction
- `get_user_supabase_client()`: Per-user Supabase client creation
- `create_signed_url()`: Secure image URL generation with time limits

### **2. Image Processing Pipeline**

**Modules:** `palette.py` (Color Analysis) + `app/services/imaging.py` + Client-side compression

```
[Client Upload] ──WebP Compression──► [Supabase Storage] ──Signed URL──► [Backend Processing]
       │                                      │                               │
   File Validation                      Private Bucket                 Color Extraction
       │                                      │                               │
   Size Limits                          Path Structure                  HSV Analysis
       │                                      │                               │
   Type Checking                        RLS Security                   Bin Classification
```

**Processing Pipeline:**
1. **Client-Side**: Image compression to WebP format (max 1024px, quality 0.6)
2. **Upload**: Secure upload to private Supabase Storage bucket
3. **Path Generation**: `wardrobe/{user_id}/{uuid}.webp` structure
4. **Color Analysis**: HSV color space conversion and K-means clustering
5. **Bin Classification**: 10-bin color system (red, orange, yellow, green, teal, blue, purple, pink, brown, neutral)

**Key Algorithms:**
- `rgb_to_hsv()`: RGB to HSV color space conversion
- `hue_to_bin()`: Hue degree mapping to color bins
- `extract_color_bins()`: Dominant color detection via clustering

### **3. Outfit Matching Engine**

**Module:** `matching.py` (Rule-based Algorithm)

```
[Source Garment] ──Color Bins──► [Matching Algorithm] ──Scoring──► [Ranked Suggestions]
       │                               │                    │              │
   Meta Tags                    Rule Application       Score Calculation   Reasons
       │                               │                    │              │
   Category                    Complementary Colors      Weight Sum      Explanations
                                      │                    │              │
                               Analogous Colors         Normalization   JSON Response
                                      │                    │
                               Neutral Pairing          Clamping
                                      │
                               Tag Overlap
```

**Scoring Algorithm:**
- **Complementary Colors** (+0.6): Blue↔Orange, Red↔Green, Yellow↔Purple
- **Neutral Pairing** (+0.4): Any color with neutral
- **Analogous Colors** (+0.2): Adjacent on color wheel
- **Shared Tags** (+0.1 each, max +0.2): Style/occasion overlap

**Communication Flow:**
1. `GET /suggest/{garment_id}` endpoint receives request
2. Source garment data fetched from database with RLS
3. Candidate garments filtered by opposite category (top↔bottom)
4. Each candidate scored using `score_and_reasons()` function
5. Results sorted, limited, and enhanced with signed URLs

### **4. Data Layer Architecture**

**Modules:** Supabase Client + PostgreSQL + RLS

```
[Frontend Queries] ──Supabase Client──► [PostgreSQL + RLS] ──Row Filtering──► [User Data]
        │                                       │                                │
   Server Actions                         Policy Engine                  JSON Response
        │                                       │                                │
   Real-time Subs                        User Context                   Type Safety
        │                                       │                                │
   Optimistic Updates                     Security Rules                Automatic Caching
```

**Database Schema:**
```sql
-- Core tables with RLS enabled
garments (id, user_id, category, image_path, color_bins, meta_tags)
events (id, user_id, event_type, timestamp_ms, data)
user_preferences (user_id, avoid_hues, prefer_neutrals, season_bias)
user_features (user_id, hue_bias, neutral_affinity, event_count)
```

**Security Policies:**
- **Read Policy**: `auth.uid() = user_id`
- **Write Policy**: `auth.uid() = user_id`
- **Storage Policy**: Private bucket with signed URL access

### **5. Phase 5 Personalization System**

**Modules:** `app/services/personalization/` + Analytics APIs

```
[User Events] ──Event Ingestion──► [Feature Computer] ──ML Pipeline──► [Personalized Ranking]
      │                                    │                                     │
  Interaction Tracking              Time-Weighted Decay              Preference Learning
      │                                    │                                     │
  Batch Processing                  Hue Bias Calculation             Score Adjustment
      │                                    │                                     │
  Real-time Capture                Preference Detection              A/B Testing
```

**Event Processing Flow:**
1. **Event Capture**: User interactions (like, view, purchase) via `/v1/events/`
2. **Feature Computation**: Time-weighted analysis of color preferences
3. **Personalization**: Dynamic scoring adjustment based on learned preferences
4. **Experimentation**: A/B testing framework for algorithm improvements

**Key Components:**
- `FeatureComputer`: Derives user preferences from interaction history
- `ExperimentManager`: Handles A/B test assignment and tracking
- `PersonalizedRanker`: Applies learned preferences to suggestion scores
- `AnalyticsEngine`: Tracks KPIs and system health

### **6. Caching & Performance Layer**

**Modules:** `app/services/cache.py` + Redis

```
[API Requests] ──Cache Check──► [Redis Layer] ──Hit/Miss──► [Database Query]
       │                            │                            │
   Response Time                Cache Keys                 Fallback Data
       │                            │                            │
   Performance                  TTL Management              Error Handling
```

**Caching Strategy:**
- **User Features**: 6-hour TTL with invalidation on preference changes
- **Signed URLs**: 24-hour TTL for UI, 2-minute for backend processing
- **Suggestion Results**: 15-minute TTL with cache warming
- **Database Connections**: Connection pooling with overflow management

### **7. Observability & Monitoring**

**Modules:** `app/services/observability/` + Metrics APIs

```
[Application Events] ──Instrumentation──► [Metrics Collection] ──Aggregation──► [Monitoring Dashboard]
         │                                        │                                    │
    Error Tracking                         Prometheus Metrics                    Health Checks
         │                                        │                                    │
    Performance                           Custom Counters                      Alert Rules
         │                                        │                                    │
    User Analytics                        Response Times                       SLA Monitoring
```

**Monitoring Capabilities:**
- **Health Endpoints**: Component-level health reporting
- **Performance Metrics**: Response time percentiles and throughput
- **Error Tracking**: Structured logging with correlation IDs
- **Business Metrics**: User engagement and suggestion effectiveness

### **8. Security & Compliance**

**Modules:** `app/services/security/` + Input Validation

```
[API Requests] ──Rate Limiting──► [Input Validation] ──Audit Logging──► [Secure Processing]
       │                               │                       │                │
   Client Protection              XSS Prevention         Compliance          Data Access
       │                               │                       │                │
   DDoS Prevention               SQL Injection           GDPR Support        Encryption
```

**Security Layers:**
- **Rate Limiting**: Sliding window algorithm (60/min profiles, 1000/min events)
- **Input Validation**: Comprehensive sanitization with pattern detection
- **Audit Logging**: 13 event types for compliance tracking
- **Data Encryption**: Optional PII encryption with Fernet

---

## 📊 Communication Patterns & Data Flow

### **Request Lifecycle Example: Getting Outfit Suggestions**

```
1. [Frontend] User clicks "Get Suggestions" on item detail page
   ↓
2. [Frontend] createSupabaseServerClient() gets session token
   ↓
3. [Frontend] fetchSuggestions() calls GET /suggest/{id} with Bearer token
   ↓
4. [Backend] get_user_id() validates JWT with Supabase Auth API
   ↓
5. [Backend] Database query with RLS: SELECT garments WHERE user_id = ?
   ↓
6. [Backend] score_and_reasons() processes candidates with matching algorithm
   ↓
7. [Backend] create_signed_url() generates 24h URLs for suggestion images
   ↓
8. [Backend] Returns JSON with scored suggestions and explanations
   ↓
9. [Frontend] SuggestionsGrid component renders results with scores/reasons
```

### **Event Flow: User Interaction Tracking**

```
1. [Frontend] User likes/views suggestion (onClick handler)
   ↓
2. [Frontend] Event data captured: {type: 'like', suggestion_id, colors}
   ↓
3. [Frontend] POST /v1/events/single with event payload
   ↓
4. [Backend] Input validation and user authentication
   ↓
5. [Backend] Event stored in PostgreSQL events table
   ↓
6. [Background] FeatureComputer processes events in batches
   ↓
7. [Background] User preferences updated with time-weighted learning
   ↓
8. [Cache] Feature cache invalidated, triggers recomputation
```

### **Image Upload Pipeline**

```
1. [Frontend] User selects image file (onChange handler)
   ↓
2. [Frontend] Client-side compression: Canvas API → WebP conversion
   ↓
3. [Frontend] Upload to Supabase Storage: POST /storage/v1/object/
   ↓
4. [Frontend] Call backend: POST /garments with image path
   ↓
5. [Backend] Download image via signed URL for processing
   ↓
6. [Backend] Color extraction: RGB → HSV → K-means → Bins
   ↓
7. [Backend] Store garment record with color_bins and meta_tags
   ↓
8. [Frontend] Redirect to wardrobe page with new item visible
```

---

## 💻 Technology Stack

### Frontend Technologies

| Technology | Version | Purpose |
|------------|---------|---------|
| **Next.js** | 15.5.2 | React framework with App Router |
| **React** | 19.1.0 | UI library |
| **TypeScript** | 5.x | Type safety |
| **Tailwind CSS** | 4.x | Utility-first styling |
| **Supabase Client** | 2.56.1 | Database & auth integration |
| **Heroicons** | 2.2.0 | SVG icon library |

**Frontend Capabilities:**
- ✅ **Server-Side Rendering (SSR)** with Next.js App Router
- ✅ **Client-Side Image Compression** (WebP, max 1024px, quality 0.6)
- ✅ **Real-time Authentication** with session persistence
- ✅ **Responsive Design** optimized for mobile and desktop
- ✅ **Type-Safe API Integration** with TypeScript
- ✅ **Protected Route Guards** for authenticated users
- ✅ **Progressive Web App** features ready

### Backend Technologies

| Technology | Version | Purpose |
|------------|---------|---------|
| **FastAPI** | 0.104.1 | Modern Python web framework |
| **Python** | 3.13+ | Runtime environment |
| **Uvicorn** | 0.24.0 | ASGI server |
| **Pydantic** | 2.8.x | Data validation |
| **NumPy** | 1.24+ | Numerical computations |
| **OpenCV** | 4.10.x | Computer vision |
| **Pillow** | 10.0+ | Image processing |
| **scikit-learn** | 1.5.x | Machine learning utilities |
| **Rembg** | 2.0.x | Background removal |
| **psycopg2** | 2.9+ | PostgreSQL adapter |

**Backend Capabilities:**
- ✅ **RESTful API Design** with automatic OpenAPI documentation
- ✅ **JWT Authentication** with Supabase integration
- ✅ **Advanced Image Processing** with color extraction
- ✅ **Computer Vision Pipeline** for garment analysis
- ✅ **Rule-Based Matching Engine** with explainable AI
- ✅ **Background Removal** using deep learning models
- ✅ **Rate Limiting & Security** middleware
- ✅ **CORS Configuration** for secure cross-origin requests

### Database & Infrastructure

| Technology | Purpose |
|------------|---------|
| **Supabase** | Backend-as-a-Service platform |
| **PostgreSQL** | Primary database with JSON support |
| **Row Level Security (RLS)** | Per-user data isolation |
| **Supabase Storage** | Private file storage with signed URLs |
| **Supabase Auth** | JWT-based authentication |
| **Redis** | Caching layer (Phase 4+) |

---

## 🚀 Core Features & Capabilities

### 1. Authentication & Security
- **Multi-provider Authentication** (Email/Password, OAuth ready)
- **JWT Token Management** with automatic refresh
- **Row-Level Security** ensuring user data isolation
- **Private Storage** with time-limited signed URLs
- **Input Validation** with SQL injection protection
- **Rate Limiting** per endpoint category
- **Audit Logging** for compliance (GDPR ready)
- **Data Encryption** for sensitive information

### 2. Image Processing & Analysis
- **Client-Side Compression** (WebP format, optimized sizes)
- **Advanced Color Extraction** using HSV color space
- **Color Binning Algorithm** (10 fixed bins: red, orange, yellow, green, teal, blue, purple, pink, brown, neutral)
- **Background Removal** using AI models
- **Meta-tag Generation** (automatic style/garment classification)
- **Image Optimization** for web delivery
- **Signed URL Generation** for secure image access

### 3. Wardrobe Management
- **Garment Upload & Tagging** with automatic categorization
- **Category Organization** (tops, bottoms, one-piece)
- **Advanced Filtering** by color, category, and tags
- **Search Functionality** across garment metadata
- **Pagination Support** for large wardrobes
- **Bulk Operations** for wardrobe management
- **Data Export/Import** capabilities

### 4. Outfit Suggestion Engine
- **Rule-Based Matching** (no ML in MVP, explainable results)
- **Color Harmony Algorithm** using color theory:
  - Complementary colors (+0.6 score)
  - Neutral pairing (+0.4 score)
  - Analogous colors (+0.2 score)
  - Shared tags (+0.1 each, capped)
- **Explainable Recommendations** with reason breakdown
- **Score Visualization** (percentage + strength indicators)
- **Real-time Suggestions** (<500ms response time)
- **Configurable Result Limits** (1-50 suggestions)

### 5. Phase 5: Advanced Personalization (In Progress)
- **User Preference Learning** from interaction history
- **Time-Weighted Feature Computation** for evolving tastes
- **A/B Experiment Framework** for algorithm testing
- **Advanced Analytics Dashboard** with KPIs
- **Personalized Ranking** based on user behavior
- **Event Tracking** for suggestion effectiveness
- **Cache Optimization** for performance

---

## 📁 Project Structure

```
what2wear/
├── frontend/                    # Next.js application
│   ├── src/app/                # App Router pages
│   │   ├── (app)/             # Protected routes
│   │   │   ├── wardrobe/      # Wardrobe management
│   │   │   ├── upload/        # Image upload
│   │   │   └── item/[id]/     # Item details & suggestions
│   │   ├── login/             # Authentication pages
│   │   └── signup/            
│   ├── lib/                   # Utility libraries
│   │   ├── auth.ts           # Authentication helpers
│   │   ├── supabaseClient.ts # Database client
│   │   ├── storage.ts        # File operations
│   │   └── suggestions.ts    # Suggestion API
│   └── types/                # TypeScript definitions
│
├── backend/                    # FastAPI application
│   ├── app/                   # Application modules
│   │   ├── api/              # API endpoints
│   │   │   ├── profile.py    # User profile management
│   │   │   ├── events.py     # Event tracking
│   │   │   └── phase5_analytics.py # Analytics
│   │   ├── services/         # Business logic
│   │   │   ├── security/     # Security services
│   │   │   ├── personalization/ # ML/AI services
│   │   │   ├── observability/ # Monitoring
│   │   │   └── colors/       # Color analysis
│   │   └── utils/            # Shared utilities
│   ├── tests/                # Comprehensive test suite
│   ├── docs/                 # API documentation
│   ├── config/               # Configuration management
│   ├── deps.py               # Dependency injection
│   ├── palette.py            # Color extraction
│   ├── matching.py           # Suggestion algorithm
│   └── main.py               # Application entry point
│
└── Project_Charter/           # Project documentation
    ├── Phase_0.md            # Project setup
    ├── Phase_1.md            # Authentication
    ├── Phase_2.md            # Image upload
    ├── Phase_3.md            # Color extraction
    ├── Phase_4.md            # Wardrobe management
    ├── Phase_5.md            # Suggestions & personalization
    └── Vision_Architecture.md # Overall architecture
```

---

## 🔌 API Endpoints

### Core Endpoints
```
GET  /healthz                    # Health check
POST /garments                   # Create garment
GET  /garments                   # List user garments
GET  /suggest/{garment_id}       # Get outfit suggestions
POST /colors/extract             # Extract colors from image
```

### Phase 5 Personalization APIs
```
GET  /v1/profile/preferences     # Get user preferences
POST /v1/profile/preferences     # Update preferences
POST /v1/profile/delete          # GDPR data deletion
POST /v1/events/single           # Track single event
POST /v1/events/batch            # Batch event tracking
GET  /v1/analytics/kpis          # System KPIs
GET  /v1/analytics/health/phase5 # System health
```

### Advanced Features
```
GET  /api/observability/metrics  # Prometheus metrics
GET  /api/observability/health   # Component health
GET  /docs                       # Interactive API documentation
```

---

## 📊 Performance Characteristics

### Response Times
- **Image Upload**: ~700ms (including compression & analysis)
- **Wardrobe Loading**: ~400ms (with pagination)
- **Outfit Suggestions**: <500ms (rule-based algorithm)
- **Color Extraction**: ~200ms (per image)
- **Authentication**: ~100ms (JWT validation)

### Scalability Features
- **Connection Pooling** (configurable pool sizes)
- **Redis Caching** with TTL management
- **Rate Limiting** (60 req/min profiles, 1000 req/min events)
- **Background Processing** for heavy computations
- **CDN-Ready** image delivery
- **Horizontal Scaling** support

### Security Measures
- **Input Validation** with XSS/SQL injection protection
- **Rate Limiting** by endpoint and user
- **JWT Authentication** with Supabase integration
- **HTTPS Enforcement** in production
- **CORS Configuration** for secure API access
- **Audit Logging** for security compliance

---

## 🧪 Testing & Quality Assurance

### Test Coverage
- **Unit Tests** for all core algorithms
- **Integration Tests** for API endpoints
- **End-to-End Tests** for complete user flows
- **Performance Tests** for response times
- **Security Tests** for vulnerability scanning

### Testing Technologies
```
pytest>=7.0.0              # Python testing framework
httpx>=0.24.0               # Async HTTP client for testing
@testing-library/react      # React component testing
jest                        # JavaScript testing framework
cypress (planned)           # E2E testing
```

### Quality Tools
- **ESLint** for JavaScript/TypeScript linting
- **Prettier** for code formatting
- **mypy** for Python type checking
- **Black** for Python code formatting
- **CI/CD Pipeline** with GitHub Actions

---

## 🔄 Development Workflow

### Environment Setup
```bash
# Quick start - runs both frontend and backend
./start-dev.sh

# Frontend only (http://localhost:3000)
cd frontend && npm run dev

# Backend only (http://localhost:8000)
cd backend && uvicorn main:app --reload
```

### Development Tools
- **Hot Reload** for both frontend and backend
- **API Documentation** at `/docs` (Swagger UI)
- **Database Migrations** via Supabase CLI
- **Environment Configuration** with .env files
- **Docker Support** for containerized deployment

---

## 🚀 Deployment & Operations

### Deployment Options
- **Vercel** (recommended for frontend)
- **Railway/Render** (for FastAPI backend)
- **Docker Containers** (full stack)
- **Supabase Hosting** (integrated solution)

### Monitoring & Observability
- **Prometheus Metrics** for performance monitoring
- **Health Checks** for all components
- **Structured Logging** with configurable levels
- **Error Tracking** with detailed stack traces
- **User Analytics** for product insights

### Configuration Management
- **Environment-Specific Settings** (dev/staging/prod)
- **Feature Flags** for gradual rollouts
- **Security Configuration** (rate limits, encryption)
- **Performance Tuning** (cache TTL, timeouts)

---

## 🔮 Future Roadmap

### Planned Enhancements
- **Machine Learning Integration** for improved suggestions
- **Weather-Based Recommendations** using location data
- **Social Features** (sharing outfits, style communities)
- **Multi-Item Outfit Creation** (3+ piece combinations)
- **Style Transfer** using computer vision
- **Voice Interface** for hands-free interaction
- **Mobile App** (React Native)
- **Augmented Reality** try-on experiences

### Technical Improvements
- **GraphQL API** for flexible data fetching
- **Real-time Notifications** via WebSockets
- **Advanced Caching** strategies
- **Microservices Architecture** for large scale
- **Event Sourcing** for data consistency
- **Kubernetes Orchestration** for auto-scaling

---

## 📈 Current Status

### Phase Completion
- ✅ **Phase 0**: Project Setup & Environment
- ✅ **Phase 1**: Authentication & User Management
- ✅ **Phase 2**: Image Upload & Storage
- ✅ **Phase 3**: Color Extraction & Analysis
- ✅ **Phase 4**: Wardrobe Management & Filtering
- ✅ **Phase 5**: Personalization Engine (Completed)

### Production Readiness
- ✅ **Security Hardened** with comprehensive protection
- ✅ **Performance Optimized** with sub-500ms response times
- ✅ **GDPR Compliant** with data export/deletion
- ✅ **Scalable Architecture** ready for growth
- ✅ **Comprehensive Testing** with high coverage
- ✅ **Documentation Complete** for all components

---

## 🤝 Contributing

### Development Environment
1. **Clone Repository**: `git clone <repository-url>`
2. **Install Dependencies**: `npm install` (frontend), `pip install -r requirements.txt` (backend)
3. **Setup Environment**: Configure `.env` files
4. **Run Tests**: `npm test` (frontend), `pytest` (backend)
5. **Start Development**: `./start-dev.sh`

### Code Standards
- **TypeScript** for all frontend code
- **Python 3.13+** for backend development
- **RESTful API** design principles
- **Component-Based Architecture** for UI
- **Test-Driven Development** practices
- **Git Flow** for version control

---

**Built with ❤️ by the What2Wear Team**  
*Empowering users to look their best, one outfit at a time.*
