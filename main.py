import json
import joblib
import pandas as pd
from fastapi import FastAPI, Request, Form, Depends, status
from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from database import SessionLocal, engine
import models

from auth import (
    get_password_hash,
    verify_password,
    get_current_user
)

import secrets


app = FastAPI()

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


cluster_actions = {
    "Low Risk": "Police surveillance, community engagement programs, intelligence monitoring.",
    "Medium Risk": "Increased patrol operations, inter-agency coordination, preventive arrests.",
    "High Risk": "Special task force deployment, military support, targeted intelligence raids.",
    "Extreme Risk": "Full military deployment, emergency response activation, federal security intervention."
}


app.mount("/static", StaticFiles(directory="static"), name="static")


models.Base.metadata.create_all(bind=engine)

templates = Jinja2Templates(directory="templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


try:
    kmeans_model = joblib.load("kmeans_model.pkl")
    scaler = joblib.load("scaler.pkl")
except Exception as e:
    print("Model loading failed:", e)
    kmeans_model = None
    scaler = None



@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})



@app.get("/register")
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    existing_user = db.query(models.User).filter(
        (models.User.username == username) |
        (models.User.email == email)
    ).first()

    if existing_user:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Username or Email already exists"}
        )

    hashed_password = get_password_hash(password)

    new_user = models.User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        role="analyst"
    )

    db.add(new_user)
    db.commit()

    return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)



@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.username == username).first()

    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid credentials"}
        )

    response = RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="user_id", value=str(user.id))
    return response



@app.get("/logout")
def logout():
    response = RedirectResponse("/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("user_id")
    return response



@app.get("/dashboard")
def dashboard(
    request: Request,
    msg: str = None,  # ✅ Capture optional message
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    history = (
        db.query(models.Prediction)
        .filter(models.Prediction.user_id == user.id)
        .order_by(models.Prediction.created_at.desc())
        .all()
    )

    # ✅ Load list of states from dataset
    data = pd.read_csv("NIGERIA_2023_CRIME_WITH_CLUSTERS.csv")
    all_states = sorted(data["State"].unique().tolist())

    # ✅ Notification logic (NEW)
    notification = None

    if msg == "cleared":
        notification = "All intelligence assessments have been cleared successfully."
    elif msg == "not_admin":
        notification = "Only administrators can clear intelligence assessments."

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "history": history,
            "all_states": all_states,
            "notification": notification  
        }
    )



@app.post("/predict")
def predict(
    request: Request,
    state: str = Form(...),
    Terrorism: float = Form(...),
    Banditry: float = Form(...),
    Murder: float = Form(...),
    Armed_Robbery: float = Form(...),
    Kidnapping: float = Form(...),
    Other: float = Form(...),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):


    data = pd.read_csv("NIGERIA_2023_CRIME_WITH_CLUSTERS.csv")
    all_states = sorted(data["State"].unique().tolist())

    # Load prediction history
    history = (
        db.query(models.Prediction)
        .filter(models.Prediction.user_id == user.id)
        .order_by(models.Prediction.created_at.desc())
        .all()
    )

    if not kmeans_model or not scaler:
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "user": user,
                "prediction": None,
                "recommended_action": "Model not available",
                "history": history,
                "all_states": all_states
            }
        )

    input_data = [[
        Terrorism,
        Banditry,
        Murder,
        Armed_Robbery,
        Kidnapping,
        Other
    ]]

    scaled_input = scaler.transform(input_data)
    cluster = int(kmeans_model.predict(scaled_input)[0])

    if cluster == 0:
        risk_level = "Moderate Risk"
        recommended_action = "Increase surveillance and intelligence monitoring."
    elif cluster == 1:
        risk_level = "Low Risk"
        recommended_action = "Maintain preventive security posture."
    elif cluster == 2:
        risk_level = "High Risk"
        recommended_action = "Deploy rapid response tactical units."
    else:
        risk_level = "Extreme Risk"
        recommended_action = "Activate national emergency security protocols."

    
    new_prediction = models.Prediction(
        user_id=user.id,
        state=state,
        Terrorism=Terrorism,
        Banditry=Banditry,
        Murder=Murder,
        Armed_Robbery=Armed_Robbery,
        Kidnapping=Kidnapping,
        Other=Other,
        cluster=cluster,
        risk_level=risk_level,
        recommendation=recommended_action
    )

    db.add(new_prediction)
    db.commit()
    db.refresh(new_prediction)

    
    history = (
        db.query(models.Prediction)
        .filter(models.Prediction.user_id == user.id)
        .order_by(models.Prediction.created_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "prediction": cluster,
            "risk_level": risk_level,
            "recommended_action": recommended_action,
            "history": history,
            "all_states": all_states
        }
    )
    
@app.post("/run-simulation")
def run_simulation(
    request: Request,
    state: str = Form(...),
    Terrorism: float = Form(...),
    Banditry: float = Form(...),
    Murder: float = Form(...),
    Armed_Robbery: float = Form(...),
    Kidnapping: float = Form(...),
    Other: float = Form(...),
    user: models.User = Depends(get_current_user)
):

    
    data = pd.read_csv("NIGERIA_2023_CRIME_WITH_CLUSTERS.csv")
    all_states = sorted(data["State"].unique().tolist())

    if not kmeans_model or not scaler:
        return templates.TemplateResponse(
            "simulation.html",
            {
                "request": request,
                "user": user,
                "prediction": None,
                "recommended_action": "Model not available",
                "all_states": all_states
            }
        )

    input_data = [[
        Terrorism,
        Banditry,
        Murder,
        Armed_Robbery,
        Kidnapping,
        Other
    ]]

    scaled_input = scaler.transform(input_data)
    cluster = kmeans_model.predict(scaled_input)[0]

    if cluster == 0:
        risk_level = "Moderate Risk"
        recommended_action = "Increase surveillance and intelligence monitoring."
    elif cluster == 1:
        risk_level = "Low Risk"
        recommended_action = "Maintain preventive security posture."
    elif cluster == 2:
        risk_level = "High Risk"
        recommended_action = "Deploy rapid response tactical units."
    else:
        risk_level = "Extreme Risk"
        recommended_action = "Activate national emergency security protocols."

    return templates.TemplateResponse(
        "simulation.html",
        {
            "request": request,
            "user": user,
            "prediction": cluster,
            "risk_level": risk_level,
            "recommended_action": recommended_action,
            "all_states": all_states
        }
    )
    
    input_data = [[
        Terrorism,
        Banditry,
        Murder,
        Armed_Robbery,
        Kidnapping,
        Other
    ]]

    scaled_data = scaler.transform(input_data)
    cluster = int(kmeans_model.predict(scaled_data)[0])

    
    risk_level = {
        0: "Moderate Risk",
        1: "Low Risk",
        2: "High Risk",
        3: "Extreme Risk"
    }.get(cluster, "Unknown")

    
    recommendation_map = {
        1: "Maintain routine surveillance operations. Strengthen community policing, intelligence monitoring, and inter-agency communication.",
        0: "Increase coordinated security patrols. Deploy targeted tactical response units and enhance intelligence gathering.",
        2: "Deploy federal intervention task forces. Expand counter-terrorism operations and reinforce rapid response units.",
        3: "Declare emergency security protocol. Mobilize military support, activate national crisis response strategy, and initiate federal security oversight."
    }

    recommended_action = recommendation_map.get(
        cluster,
        "No action defined"
    )

    
    new_prediction = models.Prediction(
        state=state,
        Terrorism=Terrorism,
        Banditry=Banditry,
        Murder=Murder,
        Armed_Robbery=Armed_Robbery,
        Kidnapping=Kidnapping,
        Other=Other,
        cluster=cluster,
        risk_level=risk_level,
        recommendation=recommended_action,  
        user_id=user.id
    )

    db.add(new_prediction)
    db.commit()

    
    history = (
        db.query(models.Prediction)
        .filter(models.Prediction.user_id == user.id)
        .order_by(models.Prediction.created_at.desc())
        .all()
    )

    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,

            # For result display section
            "prediction": {
                "cluster": cluster,
                "risk_level": risk_level,
                "recommendation": recommended_action
            },

            # For table
            "history": history,

            "state": state
        }
    )



@app.get("/analytics")
def analytics(request: Request, user: models.User = Depends(get_current_user)):

    data = pd.read_csv("NIGERIA_2023_CRIME_WITH_CLUSTERS.csv")

    risk_map = {
        0: "Moderate Risk",
        1: "Low Risk",
        2: "High Risk",
        3: "Extreme Risk"
    }

    cluster_groups = (
        data.groupby("Cluster")["State"]
        .apply(list)
        .to_dict()
    )

    cluster_counts = data["Cluster"].value_counts().to_dict()

    analytics_data = []

    for cluster, states in cluster_groups.items():
        analytics_data.append({
            "cluster": cluster,
            "risk_level": risk_map.get(cluster, "Unknown"),
            "count": cluster_counts.get(cluster, 0),
            "states": states
        })

    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request,
            "analytics_data_json": json.dumps(analytics_data),
            "user": user
        }
    )




@app.get("/admin")
def admin_panel(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    if user.role != "admin":
        return RedirectResponse("/dashboard", status_code=302)

    users = db.query(models.User).all()

    return templates.TemplateResponse(
        "admin_panel.html",
        {
            "request": request,
            "users": users,
            "user": user
        }
    )




@app.post("/admin/promote/{user_id}")
def promote_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != "admin":
        return RedirectResponse("/dashboard", status_code=302)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.role = "admin"
        db.commit()

    return RedirectResponse("/admin", status_code=302)


@app.post("/admin/demote/{user_id}")
def demote_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != "admin":
        return RedirectResponse("/dashboard", status_code=302)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.role = "analyst"
        db.commit()

    return RedirectResponse("/admin", status_code=302)


@app.post("/admin/delete/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != "admin":
        return RedirectResponse("/dashboard", status_code=302)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        db.delete(user)
        db.commit()

    return RedirectResponse("/admin", status_code=302)


@app.get("/simulation")
def simulation(
    request: Request,
    user: models.User = Depends(get_current_user)
):
    data = pd.read_csv("NIGERIA_2023_CRIME_WITH_CLUSTERS.csv")
    all_states = sorted(data["State"].unique().tolist())

    features = [
        "Terrorism",
        "Banditry",
        "Murder",
        "Armed_Robbery",
        "Kidnapping",
        "Other"
    ]

    return templates.TemplateResponse(
        "simulation.html",
        {
            "request": request,
            "user": user,
            "features": features,
            "all_states": all_states
        }
    )



reset_tokens = {}

@app.get("/reset-request")
def reset_request_page(request: Request):
    return templates.TemplateResponse("reset_request.html", {"request": request})

@app.post("/reset-request")
def reset_request(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        return templates.TemplateResponse(
            "reset_request.html",
            {"request": request, "error": "Email not found"}
        )

    token = secrets.token_urlsafe(16)
    reset_tokens[token] = user.id

    reset_link = f"{request.base_url}reset-password/{token}"

    return templates.TemplateResponse(
    "reset_request.html",
    {
        "request": request,
        "message": f"Reset link: {reset_link}"
    }
)


@app.get("/reset-password/{token}")
def reset_password_page(request: Request, token: str):
    if token not in reset_tokens:
        return RedirectResponse("/login")
    return templates.TemplateResponse("reset_password.html", {"request": request, "token": token})

@app.post("/reset-password/{token}")
def reset_password(token: str, new_password: str = Form(...), db: Session = Depends(get_db)):
    if token not in reset_tokens:
        return RedirectResponse("/login")

    user_id = reset_tokens[token]
    user = db.query(models.User).filter(models.User.id == user_id).first()

    user.hashed_password = get_password_hash(new_password)
    db.commit()

    del reset_tokens[token]
    return RedirectResponse("/login", status_code=302)

@app.on_event("startup")
def create_or_fix_admin():
    db = SessionLocal()

    admin = db.query(models.User).filter(
        models.User.username == "admin"
    ).first()

    if not admin:
        hashed_password = pwd_context.hash("admin123")

        admin = models.User(
            username="admin",
            password=hashed_password,
            role="admin",
            is_active=True,
            is_locked=False
        )
        db.add(admin)

    else:
        admin.role = "admin"
        admin.is_active = True
        admin.is_locked = False

    db.commit()
    db.close()


@app.post("/clear-history")
def clear_history(
    request: Request,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    
    if user.role.lower() != "admin":
        return RedirectResponse(
            url="/dashboard?msg=not_admin",
            status_code=303
        )

    
    db.query(models.Prediction).delete()
    db.commit()

    return RedirectResponse(
        url="/dashboard?msg=cleared",
        status_code=303
    )