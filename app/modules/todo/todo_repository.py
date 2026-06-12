from sqlalchemy.orm import Session

from app.modules.todo.todo_model import Todo


class TodoRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, title: str, description: str | None) -> Todo:
        todo = Todo(title=title, description=description)
        self.db.add(todo)
        self.db.commit()
        self.db.refresh(todo)
        return todo

    def get_all(self) -> list[Todo]:
        return self.db.query(Todo).order_by(Todo.created_at.desc()).all()

    def get_by_id(self, todo_id: int) -> Todo | None:
        return self.db.query(Todo).filter(Todo.id == todo_id).first()

    def update(self, todo: Todo, title: str | None, description: str | None, is_completed: bool | None) -> Todo:
        if title is not None:
            todo.title = title
        if description is not None:
            todo.description = description
        if is_completed is not None:
            todo.is_completed = is_completed
        self.db.commit()
        self.db.refresh(todo)
        return todo

    def delete(self, todo: Todo) -> None:
        self.db.delete(todo)
        self.db.commit()
