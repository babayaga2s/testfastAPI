# 🎮 Steam Achievements API (FastAPI)

Un backend simple en Python (FastAPI) pour interroger l'API Steam et récupérer les achievements d’un joueur sur un jeu donné.

---

## 🚀 Fonctionnalités

- Récupération des achievements d’un joueur Steam (via Steam Web API)
- API REST JSON prête à l’emploi
- Backend compatible avec déploiement Render
- CORS activé pour appels depuis un frontend (Next.js, Vercel...)

---

## 📦 Stack utilisée

- [FastAPI](https://fastapi.tiangolo.com/)
- [httpx](https://www.python-httpx.org/)
- [Uvicorn](https://www.uvicorn.org/)
- [python-dotenv](https://pypi.org/project/python-dotenv/)

---

## 🔧 Installation locale

```bash
git clone git@github.com:tonuser/tonrepo.git
cd steam_backend
python3 -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate sur Windows
pip install -r requirements.txt

