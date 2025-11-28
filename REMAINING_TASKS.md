# GreenDial - Remaining Tasks

Based on the initial requirements, the following tasks remain to fully satisfy the specification.

## Completed

| Feature | Status |
|---------|--------|
| README.md and documentation (.md files) | Done |
| Flask api_server.py on localhost:8012 | Done |
| OpenRouter /completion API integration | Done |
| S3 storage (s3://mithrilmedia/greendial/) | Done |
| HIPAA waiver on signup | Done |
| Modern health app UI (index.html) | Done |
| Chat with Doc | Done |
| Doc-based login/signup flow | Done |
| Session management | Done |
| User messaging | Done |
| Settings tab (Doc style, theme, profile) | Done |
| RCL crontab scripts for Doc messages | Done |
| Droid invocation endpoint | Done |

---

## Remaining Tasks

### 1. The Services Exchange (RSE) API Integration
**Priority: High** - COMPLETED

Integrate with RSE API at `https://rse-api.com:5003/` for periodic bid suggestions.

**Subtasks:**
- [x] Create `rse_client.py` module for RSE API calls
- [x] Implement bid fetching for categories: diet, exercise, sleep, entertainment
- [x] Add `/suggestions/<user_id>` endpoint to api_server.py
- [x] Create suggestions UI tab in index.html
- [ ] Add crontab script for periodic bid polling (optional)
- [ ] Store bid history in S3 (optional)

**API Documentation:** https://theservicesexchange.com/api_docs.html

---

### 2. Personal Data Exploration Dashboard
**Priority: High** - COMPLETED (Basic)

Expand dashboard beyond basic stats to include data visualization and exploration.

**Subtasks:**
- [x] Enhanced dashboard endpoint with trends
- [x] Goal progress display
- [ ] Health data timeline view (meals, exercise, sleep, mood)
- [ ] Weekly/monthly summaries
- [ ] Data export functionality
- [ ] Comparison views (this week vs last week)

---

### 3. Symbol System Implementation
**Priority: Medium** - COMPLETED

Complete the **SYMBOL** parsing for structured data handling.

**Subtasks:**
- [x] **SELECT** symbol: Query S3 health records, replace symbol with data
- [x] **INSERT** symbol: Parse context, extract structured data, store in S3
- [x] **AUTH** symbol: Integrate with Doc's login detection
- [x] Add new symbols: **GOAL**, **SUGGEST**

---

### 4. Reminders & Goals UI
**Priority: Medium** - COMPLETED

Backend endpoints exist but need frontend UI.

**Subtasks:**
- [x] Goals tab in UI
- [x] Create/edit/delete goals interface
- [x] Goal progress tracking (basic)
- [ ] Reminder scheduling UI
- [ ] Push notification support (future)

---

### 5. Data Analysis / Oracle Droid
**Priority: Medium**

Enable natural language queries about historical health data.

**Subtasks:**
- [ ] Implement oracle droid for data queries
- [ ] Parse user questions like "How much did I sleep last week?"
- [ ] Query S3 health records
- [ ] Generate natural language summaries
- [ ] Trend detection (improving/declining)

---

### 6. Production Deployment
**Priority: Medium**

Prepare for git-based deployment to production VM.

**Subtasks:**
- [ ] Finalize nginx.conf for production
- [ ] Create systemd service file
- [ ] Environment variable management
- [ ] SSL/HTTPS setup instructions
- [ ] Deployment script (git pull + restart)
- [ ] Health check endpoint for monitoring

---

### 7. Structured Health Data Extraction
**Priority: Medium**

Transform unstructured user input into structured records.

**Subtasks:**
- [ ] Create health data schema (diet, exercise, sleep, mood, vitals)
- [ ] LLM-based extraction from chat messages
- [ ] Automatic INSERT when health data detected
- [ ] Data validation and normalization

---

### 8. User-to-User Features
**Priority: Low**

Expand social features.

**Subtasks:**
- [ ] User discovery (opt-in)
- [ ] Send message UI
- [ ] Message threads/conversations
- [ ] Block/report functionality

---

### 9. Hashing Droid / Security
**Priority: Low**

Improve authentication security.

**Subtasks:**
- [ ] Hash passphrases with bcrypt instead of plaintext
- [ ] Session tokens with expiry
- [ ] Rate limiting
- [ ] Audit logging

---

## Quick Wins (Can be done immediately)

1. **RSE API stub** - Create placeholder integration
2. **Goal creation via chat** - "Set a goal to walk 10000 steps"
3. **Basic data visualization** - Simple charts in dashboard
4. **SELECT symbol** - Query last N health entries

---

## Estimated Effort

| Task | Effort |
|------|--------|
| RSE API Integration | 2-4 hours |
| Dashboard Expansion | 4-6 hours |
| Symbol System | 2-3 hours |
| Goals UI | 2-3 hours |
| Oracle Droid | 3-4 hours |
| Production Deploy | 2-3 hours |
| Health Data Extraction | 4-6 hours |
| User-to-User | 3-4 hours |
| Security Improvements | 2-3 hours |

**Total estimated: 24-36 hours of development**

---

## Next Steps

1. Start with **RSE API Integration** as it's core to the value proposition
2. Expand **Dashboard** for data visualization
3. Complete **Symbol System** for structured data flow
4. Add **Goals UI** for user engagement

Run `python3 api_server.py` and test at http://localhost:8012
