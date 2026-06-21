from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Azure ML Backend is running on Python 3.14!"}
