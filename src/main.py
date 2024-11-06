import json
import os
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel


class NewStudent(BaseModel):
    name: str
    age: int
    school: str


class Student(BaseModel):
    name: str
    age: int
    school: str
    id: UUID


students: list[Student] = []


def load_students():
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r") as file:
                students = json.load(file)
                for student in students:
                    student["id"] = UUID(student["id"])
                return [Student(**student) for student in students]
        except json.JSONDecodeError:
            return []
    return []


def save_students():
    with open(DB_PATH, "w") as file:
        # convert students ids to strings
        students_json = [student.model_dump(mode="json") for student in students]
        json.dump(students_json, file, indent=4)


# https://fastapi.tiangolo.com/advanced/events/
@asynccontextmanager
async def lifespan(app: FastAPI):
    global students
    students = load_students()
    yield
    save_students()


app = FastAPI(lifespan=lifespan)


DB_PATH = "students.json"

query_count = 0


@app.middleware("http")
async def count_queries(request, call_next):
    global query_count
    query_count += 1
    if (query_count % 10) == 0:
        print(f"Query count: {query_count}")
    response = await call_next(request)
    return response


@app.get("/")
def is_server_up():
    return {"message": "Server is up!"}


@app.get("/students")
def get_students(
    name: str = None, age: int = None, school: str = None
) -> list[Student]:
    result = students
    if name:
        result = [student for student in result if student["name"] == name]
    if age:
        result = [student for student in result if student["age"] == age]
    if school:
        result = [student for student in result if student["school"] == school]
    return result


@app.get("/students/{student_id}")
def get_student(student_id: UUID) -> Student:
    for student in students:
        if student.id == student_id:
            return student
    raise HTTPException(status_code=404, detail="Student not found")


@app.post("/students/")
def add_student(new_student: NewStudent, background_tasks: BackgroundTasks) -> Student:
    new_student = Student(**new_student.model_dump(), id=uuid4())
    students.append(new_student)
    background_tasks.add_task(save_students)
    return new_student


@app.put("/students/{student_id}")
def update_student(
    student_id: UUID, new_student: NewStudent, background_tasks: BackgroundTasks
) -> Student:
    for student in students:
        if student["id"] == student_id:
            student.update(new_student.model_dump())
            background_tasks.add_task(save_students)
            return student

    raise HTTPException(status_code=404, detail="Student not found")


@app.delete("/students/{student_id}")
def delete_student(student_id: UUID, background_tasks: BackgroundTasks) -> None:
    for student in students:
        if student["id"] == student_id:
            students.remove(student)
            background_tasks.add_task(save_students)
            return
    raise HTTPException(status_code=404, detail="Student not found")
