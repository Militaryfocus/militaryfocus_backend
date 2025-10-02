"""
Management команда для создания резервных копий
"""
import asyncio
from django.core.management.base import BaseCommand
from scrape_content_application.backup_system import backup_manager, backup_scheduler


class Command(BaseCommand):
    help = 'Создание резервных копий системы'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='full',
            choices=['full', 'database', 'media', 'config', 'logs'],
            help='Тип резервной копии (по умолчанию full)',
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='Показать список существующих бэкапов',
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Очистить старые бэкапы',
        )
        parser.add_argument(
            '--upload-s3',
            action='store_true',
            help='Загрузить бэкапы в S3 (если настроено)',
        )

    def handle(self, *args, **options):
        if options['list']:
            self.list_backups()
        elif options['cleanup']:
            self.cleanup_backups()
        else:
            self.create_backup(options['type'])

    def create_backup(self, backup_type):
        """Создание резервной копии"""
        self.stdout.write(
            self.style.SUCCESS(f'🔄 Создание резервной копии типа: {backup_type}')
        )
        
        try:
            if backup_type == 'full':
                result = backup_manager.create_full_backup()
            elif backup_type == 'database':
                backup_file = backup_manager.create_database_backup()
                result = {
                    'success': backup_file is not None,
                    'files': [{'type': 'database', 'path': str(backup_file)}] if backup_file else [],
                    'errors': [] if backup_file else ['Ошибка создания бэкапа базы данных']
                }
            elif backup_type == 'media':
                backup_file = backup_manager.create_media_backup()
                result = {
                    'success': backup_file is not None,
                    'files': [{'type': 'media', 'path': str(backup_file)}] if backup_file else [],
                    'errors': [] if backup_file else ['Ошибка создания бэкапа медиа файлов']
                }
            elif backup_type == 'config':
                backup_file = backup_manager.create_config_backup()
                result = {
                    'success': backup_file is not None,
                    'files': [{'type': 'config', 'path': str(backup_file)}] if backup_file else [],
                    'errors': [] if backup_file else ['Ошибка создания бэкапа конфигурации']
                }
            elif backup_type == 'logs':
                backup_file = backup_manager.create_logs_backup()
                result = {
                    'success': backup_file is not None,
                    'files': [{'type': 'logs', 'path': str(backup_file)}] if backup_file else [],
                    'errors': [] if backup_file else ['Ошибка создания бэкапа логов']
                }
            
            self.display_backup_result(result)
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'💥 Критическая ошибка: {e}')
            )

    def list_backups(self):
        """Отображение списка бэкапов"""
        self.stdout.write(
            self.style.SUCCESS('📋 Список доступных резервных копий:')
        )
        
        try:
            backups = backup_manager.get_backup_list()
            
            if not backups:
                self.stdout.write(
                    self.style.WARNING('Резервные копии не найдены')
                )
                return
            
            for i, backup in enumerate(backups[:10], 1):  # Показываем последние 10
                timestamp = backup.get('timestamp', 'Неизвестно')
                success = backup.get('success', False)
                files_count = len(backup.get('files', []))
                
                status_icon = '✅' if success else '❌'
                status_color = self.style.SUCCESS if success else self.style.ERROR
                
                self.stdout.write(f"\n{i}. {status_icon} {timestamp}")
                self.stdout.write(f"   Статус: {status_color('Успешно' if success else 'С ошибками')}")
                self.stdout.write(f"   Файлов: {files_count}")
                
                if backup.get('errors'):
                    self.stdout.write(f"   Ошибки: {'; '.join(backup['errors'][:2])}")
                
                # Показываем файлы
                for file_info in backup.get('files', [])[:3]:  # Первые 3 файла
                    size_mb = file_info.get('size', 0) / (1024 * 1024)
                    exists_icon = '📁' if file_info.get('exists', True) else '❌'
                    self.stdout.write(f"   {exists_icon} {file_info.get('type', 'unknown')}: {size_mb:.1f}MB")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка получения списка бэкапов: {e}')
            )

    def cleanup_backups(self):
        """Очистка старых бэкапов"""
        self.stdout.write(
            self.style.SUCCESS('🧹 Очистка старых резервных копий...')
        )
        
        try:
            backup_manager.cleanup_old_backups()
            self.stdout.write(
                self.style.SUCCESS('✅ Очистка завершена')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка очистки: {e}')
            )

    def display_backup_result(self, result):
        """Отображение результата создания бэкапа"""
        if result['success']:
            self.stdout.write(
                self.style.SUCCESS('✅ Резервная копия создана успешно!')
            )
            
            self.stdout.write(f"\n📊 Статистика:")
            self.stdout.write(f"   Создано файлов: {len(result.get('files', []))}")
            
            total_size = 0
            for file_info in result.get('files', []):
                size_mb = file_info.get('size', 0) / (1024 * 1024)
                total_size += size_mb
                self.stdout.write(f"   📁 {file_info.get('type', 'unknown')}: {size_mb:.1f}MB")
            
            self.stdout.write(f"   💾 Общий размер: {total_size:.1f}MB")
            
        else:
            self.stdout.write(
                self.style.ERROR('❌ Резервная копия создана с ошибками')
            )
            
            if result.get('errors'):
                self.stdout.write(f"\n🚨 Ошибки:")
                for error in result['errors']:
                    self.stdout.write(f"   • {error}")
            
            if result.get('files'):
                self.stdout.write(f"\n✅ Успешно созданные файлы:")
                for file_info in result['files']:
                    size_mb = file_info.get('size', 0) / (1024 * 1024)
                    self.stdout.write(f"   📁 {file_info.get('type', 'unknown')}: {size_mb:.1f}MB")