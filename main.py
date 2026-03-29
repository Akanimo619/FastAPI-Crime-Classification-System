import json
import joblib
import pandas as pd
import os
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from fastapi import UploadFile
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
    msg: str = None,  
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    history = (
        db.query(models.Prediction)
        .filter(models.Prediction.user_id == user.id)
        .order_by(models.Prediction.created_at.desc())
        .all()
    )

    
    data = pd.read_csv("NIGERIA_2023_CRIME_WITH_CLUSTERS.csv")
    all_states = sorted(data["State"].unique().tolist())

    
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
    timeframe: str = Form(...),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):


    data = pd.read_csv("NIGERIA_2023_CRIME_WITH_CLUSTERS.csv")
    all_states = sorted(data["State"].unique().tolist())

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

    multiplier_map = {
    "Daily": 365,
    "Weekly": 52,
    "Monthly": 12,
    "Yearly": 1
}

    multiplier = multiplier_map.get(timeframe, 1)

    Terrorism *= multiplier
    Banditry *= multiplier
    Murder *= multiplier
    Armed_Robbery *= multiplier
    Kidnapping *= multiplier
    Other *= multiplier

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


    risk_level = data[data["Cluster"] == cluster]["Risk_Level"].iloc[0]


    recommendation_map = {
    "Low Risk": "Maintain preventive security posture, community monitoring, and intelligence gathering.",
    "Moderate Risk": "Increase surveillance operations and inter-agency coordination.",
    "High Risk": "Deploy tactical response units and enhance intelligence operations.",
    "Extreme Risk": "Activate national emergency response, military intervention, and federal oversight."
}

    recommended_action = recommendation_map.get(risk_level, "No action defined")

    
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
    

@app.get("/simulation")
def simulation_page(request: Request, user: models.User = Depends(get_current_user)):
    data = pd.read_csv("NIGERIA_2023_CRIME_WITH_CLUSTERS.csv")
    all_states = sorted(data["State"].unique().tolist())

    return templates.TemplateResponse(
        "simulation.html",
        {
            "request": request,
            "user": user,
            "all_states": all_states,
            "prediction": None
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
    timeframe: str = Form(...),
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

    multiplier_map = {
    "Daily": 365,
    "Weekly": 52,
    "Monthly": 12,
    "Yearly": 1
}

    multiplier = multiplier_map.get(timeframe, 1)

    Terrorism *= multiplier
    Banditry *= multiplier
    Murder *= multiplier
    Armed_Robbery *= multiplier
    Kidnapping *= multiplier
    Other *= multiplier

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

    risk_level = data[data["Cluster"] == cluster]["Risk_Level"].iloc[0]


    recommendation_map = {
    "Low Risk": "Maintain preventive security posture, community monitoring, and intelligence gathering.",
    "Moderate Risk": "Increase surveillance operations and inter-agency coordination.",
    "High Risk": "Deploy tactical response units and enhance intelligence operations.",
    "Extreme Risk": "Activate national emergency response, military intervention, and federal oversight."
}

    recommended_action = recommendation_map.get(risk_level, "No action defined")

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
    
    


@app.get("/analytics")
def analytics(request: Request, user: models.User = Depends(get_current_user)):

    data = pd.read_csv("NIGERIA_2023_CRIME_WITH_CLUSTERS.csv")

    risk_map = {
        0: "Low Risk",
        1: "Moderate Risk",
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

@app.post("/admin/upload-dataset")
def upload_and_retrain(
    request: Request,
    file: UploadFile = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):

    if current_user.role != "admin":
        return RedirectResponse("/dashboard", status_code=302)

    try:
        
        file_location = f"uploaded_{file.filename}"
        with open(file_location, "wb") as f:
            f.write(file.file.read())

        
        data = pd.read_csv(file_location)

       
        features = [
            "Terrorism",
            "Banditry",
            "Murder",
            "Armed_Robbery",
            "Kidnapping",
            "Other"
        ]

        data[features] = data[features].fillna(data[features].median())

        X = data[features]

        X_weighted = X.copy()

        weights = {
            "Terrorism": 2.0,
            "Banditry": 1.5,
            "Kidnapping": 1.4,
            "Murder": 1.3,
            "Armed_Robbery": 1.2,
            "Other": 1.0
        }

        for col in features:
            X_weighted[col] = X_weighted[col] * weights[col]


        
        new_scaler = StandardScaler()
        X_scaled = new_scaler.fit_transform(X_weighted)

        
        new_kmeans = KMeans(n_clusters=4, random_state=42)
        clusters = new_kmeans.fit_predict(X_scaled)

        
        data["Cluster"] = clusters

        
        cluster_summary = data.groupby("Cluster")[features].mean()

        cluster_summary["Total"] = cluster_summary.sum(axis=1)

        sorted_clusters = cluster_summary.sort_values(by="Total")

        risk_labels = {
           sorted_clusters.index[0]: "Low Risk",
           sorted_clusters.index[1]: "Moderate Risk",
           sorted_clusters.index[2]: "High Risk",
           sorted_clusters.index[3]: "Extreme Risk"
      }


        data["Risk_Level"] = data["Cluster"].map(risk_labels)
        
        data.to_csv("NIGERIA_2023_CRIME_WITH_CLUSTERS.csv", index=False)
        
        joblib.dump(new_kmeans, "kmeans_model.pkl")
        joblib.dump(new_scaler, "scaler.pkl")

        global kmeans_model, scaler
        kmeans_model = new_kmeans
        scaler = new_scaler

        return RedirectResponse("/admin", status_code=302)

    except Exception as e:
        return templates.TemplateResponse(
            "admin_panel.html",
            {
                "request": request,
                "users": db.query(models.User).all(),
                "user": current_user,
                "error": f"Upload failed: {str(e)}"
            }
        )

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