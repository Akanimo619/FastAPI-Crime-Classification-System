# FastAPI-Crime-Classification-System
Nigeria Crime Risk Classification System

The Nigeria Crime Risk Classification System is a machine learning-based web application developed to analyse crime patterns across Nigeria's 36 states and classify states according to similarities in their reported crime profiles.

The project uses Nigeria's 2023 crime statistics, covering crime categories such as Terrorism, Banditry, Murder, Armed Robbery, Kidnapping and Other reported crimes. The data is organised at state level, making it possible to compare crime patterns across the country and identify groups of states with similar characteristics.

The core of the system is a K-Means clustering model. Since the project focuses on discovering patterns within the crime data rather than predicting an already-defined class, K-Means was used to group states based on similarities across the selected crime variables. Before clustering, the relevant features were standardised using a StandardScaler so that variables with different numerical ranges could be used together effectively.

The trained clustering model is saved as kmeans_model.pkl, while scaler.pkl contains the fitted scaler used during preprocessing. The resulting cluster assignments are incorporated into NIGERIA_2023_CRIME_WITH_CLUSTERS.csv and are used by the application when providing crime classification results.

The application was developed with FastAPI and extends the machine learning component into a complete web-based system. Rather than keeping the clustering model as a standalone notebook exercise, the trained model and scaler are loaded by the application so that users can interact with the classification system through a web interface.

The application also includes authentication and database functionality. User authentication is handled through auth.py, while database.py and models.py support the application's database structure and data models. The templates and static directories contain the frontend pages and styling used by the web application, while create_admin.py provides the functionality required to create an administrator account.

The main application logic is contained in main.py. It brings together the web interface, authentication, database functionality and machine learning components to provide the complete crime classification system.

The main prediction workflow is:

Crime Statistics → Feature Preparation → Standard Scaling → K-Means Clustering → Crime Classification → Web Application

The main dataset used by the system is NIGERIA_2023_CRIME_WITH_CLUSTERS.csv. The repository also contains the original uploaded 2023 crime statistics dataset and the 2021 crime statistics dataset used during the development process.

The project structure is organised as follows:

FastAPI-Crime-Classification-System/
│
├── static/
├── templates/
│
├── NIGERIA_2023_CRIME_WITH_CLUSTERS.csv
├── uploaded_NIGERIA_2021_CRIME_STATISTICS.csv
├── uploaded_NIGERIA_2023_CRIME_STATISTICS.csv
│
├── kmeans_model.pkl
├── scaler.pkl
│
├── auth.py
├── create_admin.py
├── database.py
├── main.py
├── models.py
├── Procfile
├── requirements.txt
└── README.md

To run the application locally, clone the repository and install the dependencies contained in requirements.txt.

git clone https://github.com/Akanimo619/FastAPI-Crime-Classification-System.git

cd FastAPI-Crime-Classification-System

pip install -r requirements.txt

The FastAPI application can then be started with:

uvicorn main:app --reload

Once the server is running, the application can be accessed through the local address provided by FastAPI.

This project was an opportunity to work through a complete machine learning application workflow, from preparing real-world crime data and applying unsupervised learning to integrating the trained model into a web application. It provided practical experience with K-Means clustering, feature scaling, model persistence and FastAPI, while also introducing the additional considerations involved in authentication, database management and application deployment.

The project demonstrates how an unsupervised machine learning approach can be developed into a functional web-based system rather than remaining solely within a data science notebook.

The application was previously deployed using Railway. The current deployment is not active because the Railway trial period has ended. The complete FastAPI application and machine learning components remain available in this repository for review and local deployment.

Author

Akanimo Eyoma

Data Analyst | Business Intelligence | Machine Learning

GitHub: https://github.com/Akanimo619
LinkedIn: https://www.linkedin.com/in/akanimo-eyoma-334775346
Email: eyomaakanimo@gmail.com
