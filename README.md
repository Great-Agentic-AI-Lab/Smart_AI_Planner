#  Smart Personal Planner & Assistant

AI-powered personal planner with multi-agent orchestration, intelligent task prioritization, and natural language interface.

##  Features

- **Multi-Agent Architecture**: 4 specialized AI agents working together
  - Task Planner Agent: Prioritizes and schedules tasks
  - Suggestion Agent: Recommends what to do next
  - Notification Agent: Sends reminders and motivational messages
  - Analytics Agent: Tracks patterns and insights

- **Multi-LLM Orchestration**: Primary (GPT-4) with fallback (Gemini)
- **Vector Database**: Pinecone for context-aware suggestions
- **Telegram Bot**: Natural language task management
- **REST API**: Full CRUD for tasks and events
- **React Dashboard**: Visual calendar and task tracking

##  Architecture

```
Frontend (React)  ←→  FastAPI Backend  ←→  PostgreSQL
                           ↓
                  Multi-Agent System
                           ↓
                  Multi-LLM Layer (GPT-4/Gemini)
                           ↓
                  Vector DB (Pinecone)
                           ↓
                  Telegram Bot
```

##  Quick Start (Day 1)

### Prerequisites
- Python 3.9+
- PostgreSQL 15+
- Node.js 16+
- Git

### 1. Clone Repository
```bash
git clone <your-repo-url>
cd smart-planner-ai
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup PostgreSQL
psql postgres
# In psql:
CREATE DATABASE smart_planner_db;
CREATE USER planner_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE smart_planner_db TO planner_user;
\q

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Initialize database
python scripts/setup_db.py

# Run server
uvicorn app.main:app --reload
```

Visit: http://localhost:8000/docs for API documentation

### 3. Get API Keys

#### Telegram Bot
1. Message @BotFather on Telegram
2. Send `/newbot`
3. Copy your bot token

#### OpenAI
- Visit: https://platform.openai.com/api-keys
- Create API key

#### Google Gemini
- Visit: https://makersuite.google.com/app/apikey
- Create API key

#### Pinecone
- Sign up: https://www.pinecone.io/
- Create index: `smart-planner` (dimension: 1536, metric: cosine)
- Copy API key

### 4. Test the Bot

1. Find your bot on Telegram
2. Send `/start`
3. Try commands:
   - `/help`
   - `/addtask`
   - `/listtasks`
   - `/suggest`

##  Project Structure

```
smart-planner-ai/
├── backend/
│   ├── app/
│   │   ├── models/          # Database models
│   │   ├── agents/          # AI agents
│   │   ├── llm/             # LLM providers
│   │   ├── vectordb/        # Pinecone integration
│   │   ├── telegram/        # Telegram bot
│   │   ├── api/             # REST endpoints
│   │   └── utils/           # Utilities
│   ├── scripts/             # Setup scripts
│   ├── tests/               # Tests
│   └── requirements.txt     # Dependencies
├── frontend/                # React app (Day 9-10)
└── docs/                    # Documentation
```

##  API Endpoints

### Tasks
- `POST /api/tasks/` - Create task
- `GET /api/tasks/` - List tasks
- `GET /api/tasks/{id}` - Get task
- `PUT /api/tasks/{id}` - Update task
- `DELETE /api/tasks/{id}` - Delete task
- `GET /api/tasks/suggestions/next` - Get next task suggestion

### Events
- `POST /api/events/` - Create event
- `GET /api/events/` - List events
- `GET /api/events/{id}` - Get event
- `PUT /api/events/{id}` - Update event
- `DELETE /api/events/{id}` - Delete event

### Chat
- `POST /api/chat/` - Natural language interface

##  Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app tests/
```

##  15-Day Development Plan

- **Days 1-2**:  Backend core + Telegram bot
- **Days 3-4**: LLM integration + Task Planner Agent
- **Days 5-6**: Vector DB + Suggestion Agent
- **Days 7-8**: Analytics Agent + priority engine
- **Days 9-10**: Frontend dashboard
- **Days 11-12**: Notification Agent + reminders
- **Days 13**: Deployment
- **Days 14**: Testing + bug fixes
- **Days 15**: Demo + documentation

##  Deployment

### Backend (Render)
```bash
# Connect GitHub repo to Render
# Set environment variables in Render dashboard
# Deploy!
```

### Frontend (Vercel)
```bash
cd frontend
npm run build
vercel deploy
```

##  Environment Variables

See `.env.example` for all required variables:
- Database credentials
- API keys (OpenAI, Gemini, Pinecone)
- Telegram bot token
- App settings

##  Contributing

This is a personal project for learning. Feel free to fork and experiment!

##  License

MIT

##  Acknowledgments

Built as a portfolio project to demonstrate:
- Multi-agent AI systems
- LLM orchestration with fallbacks
- Vector databases for RAG
- Production-ready FastAPI backend
- Modern React frontend

