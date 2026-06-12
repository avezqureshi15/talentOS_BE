from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.todo.todo_schema import TodoCreate, TodoResponse, TodoUpdate
from app.modules.todo.todo_service import TodoService

router = APIRouter(prefix="/todos", tags=["todos"])


@router.post("/", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
def create_todo(data: TodoCreate, db: Session = Depends(get_db)):
    service = TodoService(db)
    return service.create_todo(data)


@router.get("/", response_model=list[TodoResponse])
def get_all_todos(db: Session = Depends(get_db)):
    service = TodoService(db)
    return service.get_all_todos()


@router.get("/{todo_id}", response_model=TodoResponse)
def get_todo_by_id(todo_id: int, db: Session = Depends(get_db)):
    service = TodoService(db)
    return service.get_todo_by_id(todo_id)


@router.put("/{todo_id}", response_model=TodoResponse)
def update_todo(todo_id: int, data: TodoUpdate, db: Session = Depends(get_db)):
    service = TodoService(db)
    return service.update_todo(todo_id, data)


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    service = TodoService(db)
    service.delete_todo(todo_id)
