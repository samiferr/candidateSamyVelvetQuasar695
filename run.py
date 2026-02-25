import uvicorn

if __name__ == "__main__":
    uvicorn.run("lockstream.main:app", reload=True)