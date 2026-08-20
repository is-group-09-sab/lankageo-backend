# 🌊 LankaGeo Backend

The **LankaGeo Backend** is a Python-based geospatial backend service developed for the LankaGeo flood monitoring and risk assessment platform.

It provides RESTful APIs for **live flood detection, historical flood analysis, geospatial data management, user authentication, saved locations, and flood alert subscriptions**. The backend integrates with **Google Earth Engine**, **PostgreSQL/PostGIS**, **Supabase**, and external notification services to support data-driven flood monitoring in Sri Lanka.

---

## 📌 Features

### 🌊 Live Flood Detection
- Processes recent satellite imagery for flood detection.
- Supports **Sentinel-1 SAR imagery** for near-real-time flood analysis.
- Uses **Otsu Thresholding** for automatic flood-water classification.
- Generates flood polygons from detected flood areas.
- Provides flood results through REST API endpoints.

### 🛰️ Satellite Data Processing
- Integrates with **Google Earth Engine (GEE)**.
- Filters satellite imagery based on:
  - Location
  - Date range
  - Cloud coverage where applicable
  - Satellite availability
- Supports:
  - **Sentinel-1 SAR** for live flood detection.
  - **Sentinel-2 optical imagery** for historical flood analysis.
- Performs geospatial processing before returning results to the frontend.

### 📊 Historical Flood Analysis
- Supports analysis of historical flood events.
- Uses satellite imagery to identify previously affected areas.
- Supports multi-year flood trend analysis.
- Provides historical flood information for risk assessment.

### 🗺️ Geospatial Data Management
- Stores and processes geographic information.
- Supports spatial queries and flood polygon management.
- Uses **PostgreSQL with PostGIS** for spatial data storage.
- Provides APIs for retrieving saved locations and geographic data.

### 🔐 Authentication & Security
- Provides protected API endpoints.
- Uses **JWT-based authentication** for API authorization.
- Integrates with **Supabase Authentication**.
- Uses environment variables for sensitive configuration.
- Supports protected user-specific resources.

### 📍 Saved Locations
- Allows authenticated users to save locations.
- Provides CRUD operations for saved locations.
- Stores geographic coordinates and location information.
- Supports retrieving user-specific saved locations.

### 🚨 Flood Alert Service
- Supports location-based flood alert subscriptions.
- Allows users to define:
  - Location
  - Alert threshold
  - Contact information
- Sends notifications when flood conditions meet configured thresholds.
- Supports SMS and email notification services.

### 📧 Notification Services
- **Twilio** is used for SMS notifications.
- **Resend** is used for email notifications.
- Notification credentials are stored securely using environment variables.

---

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| **Python** | Backend programming language |
| **FastAPI** | REST API framework |
| **Uvicorn** | ASGI server |
| **Google Earth Engine** | Satellite imagery and geospatial processing |
| **Sentinel-1** | Live flood detection |
| **Sentinel-2** | Historical flood analysis |
| **PostgreSQL** | Database |
| **PostGIS** | Spatial database extension |
| **Supabase** | Authentication and database services |
| **JWT** | API authentication |
| **Twilio** | SMS notifications |
| **Resend** | Email notifications |
| **Pydantic** | Data validation and settings |
| **Python-dotenv** | Environment variable management |

---

## 📁 Project Structure

```text
lankageo-backend/
│
├── backend/
│   │
│   ├── app/
│   │   ├── main.py
│   │   │
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   └── ...
│   │   │
│   │   ├── services/
│   │   │   ├── alert_service.py
│   │   │   ├── gee_service.py
│   │   │   └── ...
│   │   │
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── core/
│   │   └── utils/
│   │
│   ├── scripts/
│   ├── tests/
│   ├── docs/
│   │
│   ├── requirements.txt
│   ├── .env
│   └── .env.example
│
├── .gitignore
└── README.md
```

> The exact folder structure may vary depending on the current implementation and additional modules added during development.

---

# 🚀 Getting Started

## Prerequisites

Before running the LankaGeo backend, make sure the following are installed:

- **Python 3.10 or higher**
- **pip**
- **Git**
- **PostgreSQL/PostGIS** or a configured Supabase database
- **Google Earth Engine account**
- Required API credentials
- Internet connection for satellite and external service access

---

## 1. Clone the Repository

```bash
git clone https://github.com/is-group-09-sab/lankageo-backend.git
cd lankageo-backend
```

If the backend application is inside a `backend` directory:

```bash
cd backend
```

---

## 2. Create a Virtual Environment

### Windows

```powershell
python -m venv venv
```

Activate the virtual environment:

```powershell
.\venv\Scripts\Activate.ps1
```

If PowerShell prevents activation, run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then activate again:

```powershell
.\venv\Scripts\Activate.ps1
```

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 3. Install Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt
```

---

# ⚙️ Environment Configuration

Create a `.env` file inside the backend directory.

Example:

```env
# Application
PORT=8000
DEBUG=True

# Database
DATABASE_URL=your_database_connection_string

# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# JWT
JWT_SECRET_KEY=your_secret_key

# Vonage
VONAGE_ACCOUNT_SID=your_vonage_account_sid
VONAGE_AUTH_TOKEN=your_vonage_auth_token
VONAGE_PHONE_NUMBER=your_vonage_phone_number

# Google Earth Engine
GEE_PROJECT_ID=your_google_cloud_project_id


# Resend
RESEND_API_KEY=your_resend_api_key
```

### ⚠️ Important

Never commit the `.env` file to GitHub.

Make sure `.gitignore` contains:

```gitignore
.env
.env.local
venv/
__pycache__/
*.pyc
```

Use `.env.example` to provide the names of required environment variables without exposing actual credentials.

---

# 🛰️ Google Earth Engine Configuration

LankaGeo uses **Google Earth Engine (GEE)** for satellite imagery processing.

The backend uses Earth Engine to:

1. Select the required geographic area.
2. Search for suitable satellite images.
3. Filter images according to the analysis period.
4. Process satellite data.
5. Detect potential flooded areas.
6. Generate geospatial flood results.
7. Return the processed information to the frontend.

### Sentinel-1

Sentinel-1 SAR imagery is primarily used for **live flood detection** because radar imagery can be used even when cloud cover affects optical imagery.

The backend applies image processing techniques such as **Otsu Thresholding** to separate potential water/flooded areas from surrounding land.

### Sentinel-2

Sentinel-2 optical imagery is used mainly for:

- Historical flood analysis
- Historical flood event comparison
- Multi-year flood trend analysis
- Historical flood risk assessment

---

# ▶️ Running the Backend

From the backend directory, run:

```bash
uvicorn app.main:app --reload
```

The server should start at:

```text
http://127.0.0.1:8000
```

or:

```text
http://localhost:8000
```

The `--reload` option automatically reloads the server when source files are changed during development.

---

# 📚 API Documentation

Because LankaGeo uses **FastAPI**, interactive API documentation is automatically available.

### Swagger UI

Open:

```text
http://127.0.0.1:8000/docs
```

### ReDoc

Open:

```text
http://127.0.0.1:8000/redoc
```

Swagger UI can be used to:

- View available API endpoints
- Inspect request parameters
- Test API requests
- View response structures
- Test authenticated endpoints

---

# 🔌 Main API Functionalities

The backend provides APIs supporting the following major application functions.

## 🔐 Authentication

Authentication-related APIs handle:

- User authentication
- Token validation
- Protected API access
- User-specific resources

JWT tokens are used to authorize requests to protected endpoints.

---

## 🌊 Live Flood Analysis

The live analysis service receives a geographic location and analysis parameters from the frontend.

A typical workflow is:

```text
User selects location
        ↓
Frontend sends API request
        ↓
FastAPI Live Analysis Endpoint
        ↓
Google Earth Engine
        ↓
Sentinel-1 SAR imagery
        ↓
Pre-processing
        ↓
Otsu Thresholding
        ↓
Flood area detection
        ↓
Flood polygons / results
        ↓
Frontend map
```

---

## 📊 Historical Analysis

Historical analysis follows a similar workflow:

```text
User selects location and date range
        ↓
Historical Analysis API
        ↓
Google Earth Engine
        ↓
Sentinel-2 imagery
        ↓
Image processing
        ↓
Historical flood detection
        ↓
Flood statistics / polygons
        ↓
Frontend visualization
```

---

# 🗺️ Saved Locations

Authenticated users can manage their saved geographic locations.

Typical operations include:

```text
Create Location
Get Locations
Update Location
Delete Location
```

Saved location information may include:

- Location name
- Latitude
- Longitude
- User ID
- Additional location metadata

---

# 🚨 Flood Alert System

The alert service allows users to subscribe to flood alerts for selected locations.

A subscription can contain information such as:

```text
User
 ↓
Selected Location
 ↓
Alert Threshold
 ↓
Notification Preference
 ↓
Flood Condition Monitoring
 ↓
Alert Trigger
 ↓
SMS / Email Notification
```

The system can use:
- **Twilio** for SMS alerts
- **Resend** for email alerts

Sensitive API credentials must always be stored in environment variables.

---

# 🗄️ Database

LankaGeo uses a relational database with spatial data support.

### PostgreSQL

PostgreSQL is used for structured application data.

### PostGIS

PostGIS extends PostgreSQL with geospatial capabilities.

It allows the backend to work with:

- Points
- Polygons
- Geographic coordinates
- Spatial relationships
- Geographic queries

This is particularly useful for storing and querying flood-affected areas and user locations.

---

# 🔒 Security

Security is an important part of the LankaGeo backend.

The project uses several security mechanisms:

### JWT Authentication

Protected API endpoints require a valid authentication token.

```text
Client
  ↓
JWT Token
  ↓
FastAPI Middleware / Dependency
  ↓
Token Validation
  ↓
Protected Endpoint
```

### Environment Variables

Sensitive information such as:

- Database credentials
- JWT secrets
- Supabase keys
- Google Earth Engine configuration
- Twilio credentials
- Resend API keys

should never be hard-coded into source code.

### Supabase Row Level Security

Where applicable, Supabase Row Level Security helps ensure that users can only access authorized user-specific data.

### Git Security

Secret credentials must not be committed to GitHub.

If a secret is accidentally exposed, it should be revoked and replaced immediately.

---

# 🧪 Testing

The project includes a test directory for backend testing.

Run tests using:

```bash
pytest
```

For more detailed output:

```bash
pytest -v
```

---

# 🐛 Troubleshooting

## Python command not recognized

Check whether Python is installed:

```bash
python --version
```

If Python is installed but not recognized, add Python to the system PATH.

---

## Virtual environment is not activated

On Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

On Linux/macOS:

```bash
source venv/bin/activate
```

---

## Uvicorn command not found

Make sure the virtual environment is activated and install dependencies:

```bash
pip install -r requirements.txt
```

You can also run:

```bash
python -m uvicorn app.main:app --reload
```

---

## `.env` configuration error

Make sure:

- Variable names are correct.
- There are no accidental spaces around values.
- Sensitive values are properly quoted when necessary.
- The `.env` file is located in the expected backend directory.

Example:

```env
DATABASE_URL=your_database_url
JWT_SECRET_KEY=your_secret_key
```

---

## Google Earth Engine errors

Check that:

1. Your Google Cloud project is correctly configured.
2. Earth Engine is enabled.
3. The required authentication credentials are available.
4. The configured project ID is correct.
5. The account has permission to use Earth Engine.

---

# 🔄 Backend Development Workflow

The backend development workflow generally follows:

```text
Frontend Request
       ↓
FastAPI API Endpoint
       ↓
Validation
       ↓
Authentication / Authorization
       ↓
Service Layer
       ↓
Database / Google Earth Engine
       ↓
Data Processing
       ↓
API Response
       ↓
Frontend
```

This separation allows the application to keep API handling, business logic, data processing, and database operations organized.

---

# 🌐 Frontend Integration

The LankaGeo backend is designed to communicate with the LankaGeo frontend through REST APIs.

The frontend is responsible for:

- User interface
- Map visualization
- Location selection
- User interaction
- Displaying flood results

The backend is responsible for:

- API processing
- Authentication
- Satellite data processing
- Flood detection
- Database operations
- Alert processing

---

# 📦 Dependencies

Main dependencies include:

```text
FastAPI
Uvicorn
Pydantic
Python-dotenv
Requests
Google Earth Engine API
PostgreSQL / PostGIS libraries
Supabase libraries
PyJWT
Resend
Pytest
```

The complete dependency list is maintained in:

```text
requirements.txt
```

Install all dependencies with:

```bash
pip install -r requirements.txt
```

---

# 🚀 Production Deployment

For production deployment:

1. Use a production-ready ASGI server configuration.
2. Set `DEBUG=False`.
3. Configure secure environment variables.
4. Use a production PostgreSQL/PostGIS database.
5. Configure HTTPS.
6. Restrict CORS origins.
7. Protect API credentials.
8. Configure logging and monitoring.
9. Do not expose development credentials.
10. Use secure authentication and authorization settings.

Example:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

# 📋 Environment Variables

| Variable | Purpose |
|---|---|
| `PORT` | Backend server port |
| `DEBUG` | Development/debug configuration |
| `DATABASE_URL` | PostgreSQL database connection |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase API key |
| `JWT_SECRET_KEY` | JWT signing/validation secret |
| `VONAGE_ACCOUNT_SID` | Vonage account identifier |
| `VONAGE_AUTH_TOKEN` | Vonage authentication token |
| `VONAGE_PHONE_NUMBER` | Vonage sender number |
| `GEE_PROJECT_ID` | Google Earth Engine project |
| `RESEND_API_KEY` | Resend email service key |

> The actual values must never be committed to the repository.

---

# 🤝 Contributors

Thanks to all team members who contributed to the LankaGeo project:

- [@kirperera](https://github.com/kirperera)
- [@kasunihansani](https://github.com/kasunihansani)
- [@ChathuminiWelengodage](https://github.com/ChathuminiWelengodage)
- [@BIHF](https://github.com/BIHF)
- [@PoojaniGeehara](https://github.com/PoojaniGeehara)
