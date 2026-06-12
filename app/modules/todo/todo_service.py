from sqlalchemy.orm import Session

from app.common.exceptions.todo_exception import TodoNotFoundException
from app.core.logger import get_logger
from app.modules.todo.todo_repository import TodoRepository
from app.modules.todo.todo_schema import TodoCreate, TodoResponse, TodoUpdate

logger = get_logger(__name__)


class TodoService:
    def __init__(self, db: Session):
        self.repository = TodoRepository(db)

    def create_todo(self, data: TodoCreate) -> TodoResponse:
        logger.info("Creating todo: title=%s", data.title)
        todo = self.repository.create(title=data.title, description=data.description)
        logger.debug("Todo created: id=%d", todo.id)
        return TodoResponse.model_validate(todo)

    def get_all_todos(self) -> list[TodoResponse]:
        logger.info("Fetching all todos")
        todos = self.repository.get_all()
        logger.debug("Found %d todos", len(todos))
        return [TodoResponse.model_validate(t) for t in todos]

    def get_todo_by_id(self, todo_id: int) -> TodoResponse:
        logger.info("Fetching todo: id=%d", todo_id)
        todo = self.repository.get_by_id(todo_id)
        if not todo:
            logger.error("Todo not found: id=%d", todo_id)
            raise TodoNotFoundException(todo_id)
        return TodoResponse.model_validate(todo)

    def update_todo(self, todo_id: int, data: TodoUpdate) -> TodoResponse:
        logger.info("Updating todo: id=%d", todo_id)
        todo = self.repository.get_by_id(todo_id)
        if not todo:
            logger.error("Todo not found for update: id=%d", todo_id)
            raise TodoNotFoundException(todo_id)
        updated = self.repository.update(
            todo,
            title=data.title,
            description=data.description,
            is_completed=data.is_completed,
        )
        logger.info("Todo updated: id=%d", todo_id)
        return TodoResponse.model_validate(updated)

    def delete_todo(self, todo_id: int) -> None:
        logger.info("Deleting todo: id=%d", todo_id)
        todo = self.repository.get_by_id(todo_id)
        if not todo:
            logger.error("Todo not found for delete: id=%d", todo_id)
            raise TodoNotFoundException(todo_id)
        self.repository.delete(todo)
        logger.info("Todo deleted: id=%d", todo_id)
