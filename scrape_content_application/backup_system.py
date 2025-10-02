"""
Система автоматического резервного копирования
"""
import os
import shutil
import gzip
import json
import logging
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import tarfile
import hashlib
import boto3
from botocore.exceptions import ClientError
import sys

# Добавляем путь к проекту
sys.path.append('/workspace')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'war_site.settings')

import django
django.setup()

from django.core.management import call_command
from django.conf import settings
from django.utils import timezone
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class BackupManager:
    """Менеджер резервного копирования"""
    
    def __init__(self):
        self.backup_dir = Path('/workspace/backups')
        self.backup_dir.mkdir(exist_ok=True)
        
        # Настройки хранения
        self.keep_daily_backups = 7    # Дневные бэкапы - 7 дней
        self.keep_weekly_backups = 4   # Недельные бэкапы - 4 недели
        self.keep_monthly_backups = 12 # Месячные бэкапы - 12 месяцев
        
        # AWS S3 настройки (опционально)
        self.s3_bucket = os.environ.get('BACKUP_S3_BUCKET')
        self.s3_client = None
        if self.s3_bucket:
            try:
                self.s3_client = boto3.client('s3')
            except Exception as e:
                logger.warning(f"Не удалось инициализировать S3 клиент: {e}")
    
    def create_database_backup(self) -> Optional[Path]:
        """Создание резервной копии базы данных"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"database_backup_{timestamp}.json"
        backup_path = self.backup_dir / backup_filename
        
        try:
            # Используем Django dumpdata для создания бэкапа
            with open(backup_path, 'w', encoding='utf-8') as f:
                call_command('dumpdata', 
                           '--natural-foreign', 
                           '--natural-primary',
                           '--indent', '2',
                           stdout=f)
            
            # Сжимаем файл
            compressed_path = backup_path.with_suffix('.json.gz')
            with open(backup_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Удаляем несжатый файл
            backup_path.unlink()
            
            logger.info(f"Создан бэкап базы данных: {compressed_path}")
            return compressed_path
            
        except Exception as e:
            logger.error(f"Ошибка создания бэкапа базы данных: {e}")
            if backup_path.exists():
                backup_path.unlink()
            return None
    
    def create_media_backup(self) -> Optional[Path]:
        """Создание резервной копии медиа файлов"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"media_backup_{timestamp}.tar.gz"
        backup_path = self.backup_dir / backup_filename
        
        media_dir = Path('/workspace/media')
        
        if not media_dir.exists() or not any(media_dir.iterdir()):
            logger.info("Медиа директория пуста, пропускаем бэкап")
            return None
        
        try:
            with tarfile.open(backup_path, 'w:gz') as tar:
                tar.add(media_dir, arcname='media')
            
            logger.info(f"Создан бэкап медиа файлов: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Ошибка создания бэкапа медиа файлов: {e}")
            if backup_path.exists():
                backup_path.unlink()
            return None
    
    def create_logs_backup(self) -> Optional[Path]:
        """Создание резервной копии логов"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"logs_backup_{timestamp}.tar.gz"
        backup_path = self.backup_dir / backup_filename
        
        logs_dir = Path('/workspace/logs')
        
        if not logs_dir.exists() or not any(logs_dir.iterdir()):
            logger.info("Директория логов пуста, пропускаем бэкап")
            return None
        
        try:
            with tarfile.open(backup_path, 'w:gz') as tar:
                for log_file in logs_dir.glob('*.log*'):
                    tar.add(log_file, arcname=f'logs/{log_file.name}')
            
            logger.info(f"Создан бэкап логов: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Ошибка создания бэкапа логов: {e}")
            if backup_path.exists():
                backup_path.unlink()
            return None
    
    def create_config_backup(self) -> Optional[Path]:
        """Создание резервной копии конфигурации"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"config_backup_{timestamp}.tar.gz"
        backup_path = self.backup_dir / backup_filename
        
        try:
            with tarfile.open(backup_path, 'w:gz') as tar:
                # Настройки Django
                settings_file = Path('/workspace/war_site/settings.py')
                if settings_file.exists():
                    tar.add(settings_file, arcname='settings.py')
                
                # URLs
                urls_file = Path('/workspace/war_site/urls.py')
                if urls_file.exists():
                    tar.add(urls_file, arcname='urls.py')
                
                # Requirements
                req_file = Path('/workspace/requirements.txt')
                if req_file.exists():
                    tar.add(req_file, arcname='requirements.txt')
                
                # Docker файлы
                docker_files = [
                    Path('/workspace/Dockerfile'),
                    Path('/workspace/docker-compose.yml'),
                    Path('/workspace/nginx.conf')
                ]
                
                for docker_file in docker_files:
                    if docker_file.exists():
                        tar.add(docker_file, arcname=docker_file.name)
            
            logger.info(f"Создан бэкап конфигурации: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Ошибка создания бэкапа конфигурации: {e}")
            if backup_path.exists():
                backup_path.unlink()
            return None
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """Вычисление хеша файла"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def create_full_backup(self) -> Dict[str, Any]:
        """Создание полного резервного копирования"""
        backup_info = {
            'timestamp': datetime.now().isoformat(),
            'type': 'full',
            'files': [],
            'success': True,
            'errors': []
        }
        
        logger.info("Начинаем создание полного бэкапа")
        
        # Создаем бэкапы различных компонентов
        backup_tasks = [
            ('database', self.create_database_backup),
            ('media', self.create_media_backup),
            ('logs', self.create_logs_backup),
            ('config', self.create_config_backup)
        ]
        
        for task_name, task_func in backup_tasks:
            try:
                backup_file = task_func()
                if backup_file:
                    file_info = {
                        'type': task_name,
                        'filename': backup_file.name,
                        'path': str(backup_file),
                        'size': backup_file.stat().st_size,
                        'hash': self.calculate_file_hash(backup_file)
                    }
                    backup_info['files'].append(file_info)
                    
                    # Загружаем в S3 если настроено
                    if self.s3_client:
                        self.upload_to_s3(backup_file, task_name)
                        
            except Exception as e:
                error_msg = f"Ошибка в задаче {task_name}: {e}"
                logger.error(error_msg)
                backup_info['errors'].append(error_msg)
                backup_info['success'] = False
        
        # Сохраняем информацию о бэкапе
        self.save_backup_info(backup_info)
        
        # Очищаем старые бэкапы
        self.cleanup_old_backups()
        
        logger.info(f"Полный бэкап завершен. Создано файлов: {len(backup_info['files'])}")
        return backup_info
    
    def upload_to_s3(self, file_path: Path, backup_type: str) -> bool:
        """Загрузка файла в S3"""
        if not self.s3_client or not self.s3_bucket:
            return False
        
        try:
            s3_key = f"backups/{backup_type}/{file_path.name}"
            
            self.s3_client.upload_file(
                str(file_path),
                self.s3_bucket,
                s3_key,
                ExtraArgs={
                    'ServerSideEncryption': 'AES256',
                    'Metadata': {
                        'backup_type': backup_type,
                        'created_at': datetime.now().isoformat()
                    }
                }
            )
            
            logger.info(f"Файл {file_path.name} загружен в S3: {s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Ошибка загрузки в S3: {e}")
            return False
    
    def save_backup_info(self, backup_info: Dict[str, Any]):
        """Сохранение информации о бэкапе"""
        info_filename = f"backup_info_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        info_path = self.backup_dir / info_filename
        
        try:
            with open(info_path, 'w', encoding='utf-8') as f:
                json.dump(backup_info, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Информация о бэкапе сохранена: {info_path}")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения информации о бэкапе: {e}")
    
    def cleanup_old_backups(self):
        """Очистка старых бэкапов"""
        try:
            now = datetime.now()
            
            # Получаем все файлы бэкапов
            backup_files = []
            for pattern in ['database_backup_*.json.gz', 'media_backup_*.tar.gz', 
                          'logs_backup_*.tar.gz', 'config_backup_*.tar.gz']:
                backup_files.extend(self.backup_dir.glob(pattern))
            
            # Группируем по типам и датам
            files_by_type = {}
            for file_path in backup_files:
                try:
                    # Извлекаем дату из имени файла
                    parts = file_path.stem.split('_')
                    if len(parts) >= 3:
                        date_str = parts[-2] + '_' + parts[-1].split('.')[0]
                        file_date = datetime.strptime(date_str, '%Y%m%d_%H%M%S')
                        
                        backup_type = '_'.join(parts[:-2])
                        
                        if backup_type not in files_by_type:
                            files_by_type[backup_type] = []
                        
                        files_by_type[backup_type].append((file_path, file_date))
                        
                except ValueError:
                    continue
            
            # Очищаем старые файлы для каждого типа
            for backup_type, files in files_by_type.items():
                files.sort(key=lambda x: x[1], reverse=True)  # Сортируем по дате (новые первые)
                
                files_to_delete = []
                
                for i, (file_path, file_date) in enumerate(files):
                    age_days = (now - file_date).days
                    
                    # Определяем, нужно ли удалить файл
                    should_delete = False
                    
                    if age_days > self.keep_monthly_backups * 30:
                        should_delete = True
                    elif age_days > self.keep_weekly_backups * 7:
                        # Оставляем только месячные бэкапы (первый день месяца)
                        if file_date.day != 1:
                            should_delete = True
                    elif age_days > self.keep_daily_backups:
                        # Оставляем только недельные бэкапы (воскресенье)
                        if file_date.weekday() != 6:
                            should_delete = True
                    
                    if should_delete:
                        files_to_delete.append(file_path)
                
                # Удаляем файлы
                for file_path in files_to_delete:
                    try:
                        file_path.unlink()
                        logger.info(f"Удален старый бэкап: {file_path.name}")
                    except Exception as e:
                        logger.error(f"Ошибка удаления файла {file_path}: {e}")
            
            # Очищаем старые info файлы
            info_files = list(self.backup_dir.glob('backup_info_*.json'))
            info_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            for info_file in info_files[50:]:  # Оставляем последние 50
                try:
                    info_file.unlink()
                    logger.info(f"Удален старый info файл: {info_file.name}")
                except Exception as e:
                    logger.error(f"Ошибка удаления info файла {info_file}: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка очистки старых бэкапов: {e}")
    
    def restore_database_backup(self, backup_file: Path) -> bool:
        """Восстановление базы данных из бэкапа"""
        try:
            # Распаковываем файл если он сжат
            if backup_file.suffix == '.gz':
                temp_file = backup_file.with_suffix('')
                with gzip.open(backup_file, 'rb') as f_in:
                    with open(temp_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                json_file = temp_file
            else:
                json_file = backup_file
            
            # Восстанавливаем данные
            with open(json_file, 'r', encoding='utf-8') as f:
                call_command('loaddata', f.name)
            
            # Удаляем временный файл
            if json_file != backup_file:
                json_file.unlink()
            
            logger.info(f"База данных восстановлена из {backup_file}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка восстановления базы данных: {e}")
            return False
    
    def get_backup_list(self) -> List[Dict[str, Any]]:
        """Получение списка доступных бэкапов"""
        backups = []
        
        # Получаем все info файлы
        info_files = list(self.backup_dir.glob('backup_info_*.json'))
        info_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        for info_file in info_files:
            try:
                with open(info_file, 'r', encoding='utf-8') as f:
                    backup_info = json.load(f)
                
                # Проверяем существование файлов
                existing_files = []
                for file_info in backup_info.get('files', []):
                    file_path = Path(file_info['path'])
                    if file_path.exists():
                        file_info['exists'] = True
                        existing_files.append(file_info)
                    else:
                        file_info['exists'] = False
                
                backup_info['files'] = existing_files
                backup_info['info_file'] = str(info_file)
                backups.append(backup_info)
                
            except Exception as e:
                logger.error(f"Ошибка чтения info файла {info_file}: {e}")
        
        return backups


# Планировщик бэкапов
class BackupScheduler:
    """Планировщик автоматических бэкапов"""
    
    def __init__(self):
        self.backup_manager = BackupManager()
    
    async def run_scheduled_backup(self, backup_type: str = 'full'):
        """Запуск запланированного бэкапа"""
        logger.info(f"Запуск запланированного бэкапа: {backup_type}")
        
        try:
            if backup_type == 'full':
                result = self.backup_manager.create_full_backup()
            else:
                # Можно добавить другие типы бэкапов
                result = self.backup_manager.create_full_backup()
            
            # Отправляем уведомление о результате
            await self.send_backup_notification(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка запланированного бэкапа: {e}")
            await self.send_backup_notification({
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            return None
    
    async def send_backup_notification(self, backup_result: Dict[str, Any]):
        """Отправка уведомления о результате бэкапа"""
        try:
            # Здесь можно интегрировать с системой уведомлений
            # Например, отправить webhook или email
            
            if backup_result['success']:
                message = f"✅ Бэкап успешно создан в {backup_result['timestamp']}"
                message += f"\nФайлов создано: {len(backup_result.get('files', []))}"
            else:
                message = f"❌ Ошибка создания бэкапа в {backup_result['timestamp']}"
                message += f"\nОшибки: {'; '.join(backup_result.get('errors', []))}"
            
            logger.info(f"Уведомление о бэкапе: {message}")
            
            # Здесь можно добавить отправку через webhook систему
            # await WebhookTrigger.backup_completed(backup_result)
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о бэкапе: {e}")


# Глобальный экземпляр
backup_manager = BackupManager()
backup_scheduler = BackupScheduler()