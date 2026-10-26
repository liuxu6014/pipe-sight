from collections.abc import Generator
from pathlib import Path

from app.infrastructure.schemas.files import UploadResponseModel
from app.infrastructure.services.file_storage import FileStorageService
from app.infrastructure.services.file_upload import FileUploadSupport
from common.http.schemas import CrudResponseModel
from common.ports.background_tasks import BackgroundTasksPort
from common.ports.files import UploadFilePort
from config.env import UploadConfig
from exceptions.exception import ServiceException


class FileTransferService:
    """通用文件上传、下载和资源访问服务。"""

    @staticmethod
    def bytes_to_stream(content: bytes) -> Generator[bytes]:
        """将内存中的文件内容包装为流式响应可消费的迭代器。"""
        yield content

    @staticmethod
    def _safe_path(root: str, user_path: str) -> Path:
        """Resolve a client path and keep it inside the configured root."""
        root_path = Path(root).resolve()
        candidate = (root_path / user_path).resolve()
        try:
            candidate.relative_to(root_path)
        except ValueError as error:
            raise ServiceException(message='文件名称不合法') from error
        return candidate

    @classmethod
    async def upload_service(cls, base_url: str, file: UploadFilePort) -> CrudResponseModel:
        """
        通用上传service

        :param base_url: 应用基础URL
        :param file: 上传文件对象
        :return: 上传结果
        """
        stored = await FileStorageService.upload(base_url, file)
        return CrudResponseModel(
            is_success=True,
            result=UploadResponseModel(
                file_name=stored.file_name,
                new_file_name=stored.new_file_name,
                original_filename=stored.original_filename,
                url=stored.url,
            ),
            message='上传成功',
        )

    @classmethod
    async def download_services(
        cls, background_tasks: BackgroundTasksPort, file_name: str, delete: bool
    ) -> CrudResponseModel:
        """
        下载下载目录文件service

        :param background_tasks: 后台任务对象
        :param file_name: 下载的文件名称
        :param delete: 是否在下载完成后删除文件
        :return: 上传结果
        """
        filepath = cls._safe_path(UploadConfig.DOWNLOAD_PATH, file_name)
        if not filepath.is_file() or not FileUploadSupport.check_file_exists(str(filepath)):
            raise ServiceException(message='文件不存在')
        if delete:
            background_tasks.add_task(FileUploadSupport.delete_file, str(filepath))
        return CrudResponseModel(
            is_success=True,
            result=FileUploadSupport.generate_file(str(filepath)),
            message='下载成功',
        )

    @classmethod
    async def download_resource_services(cls, resource: str) -> CrudResponseModel:
        """
        下载上传目录文件service

        :param resource: 下载的文件名称
        :return: 上传结果
        """
        prefix = f'{UploadConfig.UPLOAD_PREFIX}/'
        if not resource.startswith(prefix):
            raise ServiceException(message='文件名称不合法')
        relative_resource = resource[len(prefix):]
        filepath = cls._safe_path(UploadConfig.UPLOAD_PATH, relative_resource)
        filename = Path(relative_resource).name
        if (
            '..' in filename
            or not FileUploadSupport.check_file_timestamp(filename)
            or not FileUploadSupport.check_file_machine(filename)
            or not FileUploadSupport.check_file_random_code(filename)
        ):
            raise ServiceException(message='文件名称不合法')
        if not filepath.is_file() or not FileUploadSupport.check_file_exists(str(filepath)):
            raise ServiceException(message='文件不存在')
        return CrudResponseModel(
            is_success=True,
            result=FileUploadSupport.generate_file(str(filepath)),
            message='下载成功',
        )


__all__ = ['FileTransferService']
