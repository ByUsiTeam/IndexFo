#!/usr/bin/env python3
"""
ByUsiCDN - Index Fo 服务器
支持URL参数路径分享和优化的UI
"""

import http.server
import socketserver
import os
import json
import urllib.parse
import logging
from datetime import datetime
from pathlib import Path
import sys
from typing import Dict, Any

# 配置Rich日志
try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.traceback import install as install_rich_traceback
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.panel import Panel
    from rich.table import Table
    
    # 安装Rich回溯处理
    install_rich_traceback(show_locals=True)
    
    # 配置Rich日志处理器
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)]
    )
    
    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 配置
CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    "cdn_data_folder": "cdnData",
    "theme_color": "#FF0000",
    "blur_intensity": "25px",
    "site_title": "ByUsiCDN - Index Fo",
    "html_file": "index.html"
}

class ByUsiCDNRequestHandler(http.server.SimpleHTTPRequestHandler):
    """ByUsiCDN自定义请求处理器"""
    
    def __init__(self, *args, **kwargs):
        self.cdn_path = Path(CONFIG["cdn_data_folder"])
        self.html_content = self.load_html_template()
        super().__init__(*args, **kwargs)
    
    def load_html_template(self) -> str:
        """加载HTML模板文件"""
        html_file = Path(CONFIG["html_file"])
        if not html_file.exists():
            self.log_error("HTML模板文件不存在: %s", CONFIG["html_file"])
            return self.generate_fallback_html()
        
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.log_error("读取HTML模板失败: %s", str(e))
            return self.generate_fallback_html()
    
    def generate_fallback_html(self) -> str:
        """生成备用HTML内容"""
        return '''
<!DOCTYPE html>
<html>
<head>
    <title>ByUsiCDN - 错误</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 50px; text-align: center; }
        .error { color: #FF0000; background: #ffe6e6; padding: 20px; border-radius: 10px; }
    </style>
</head>
<body>
    <div class="error">
        <h1>⚠️ 系统错误</h1>
        <p>无法加载界面模板，请检查 index.html 文件是否存在</p>
    </div>
</body>
</html>'''
    
    def log_message(self, format, *args):
        """使用Rich输出日志"""
        if HAS_RICH:
            console.log(f"[cyan]{self.address_string()}[/cyan] - {format % args}")
        else:
            super().log_message(format, *args)
    
    def log_error(self, format, *args):
        """使用Rich输出错误日志"""
        if HAS_RICH:
            console.log(f"[red]ERROR[/red] - {format % args}")
        else:
            super().log_error(format, *args)
    
    def do_GET(self):
        """处理GET请求"""
        try:
            parsed_path = urllib.parse.urlparse(self.path)
            path = parsed_path.path
            query_params = urllib.parse.parse_qs(parsed_path.query)
            
            if path == '/':
                # 处理根路径，支持path参数
                target_path = query_params.get('path', [''])[0]
                self.serve_index(target_path)
            elif path == '/api/files':
                # 支持路径参数
                target_path = query_params.get('path', [''])[0]
                self.serve_files_api(target_path)
            elif path.startswith('/download/'):
                self.serve_file_download(path)
            elif path == '/api/stats':
                self.serve_stats_api()
            elif path == '/api/navigate':
                # 文件夹导航API
                target_path = query_params.get('path', [''])[0]
                self.serve_navigate_api(target_path)
            else:
                # 默认文件服务
                super().do_GET()
                
        except Exception as e:
            self.log_error("处理请求时出错: %s", str(e))
            self.send_error(500, f"服务器内部错误: {str(e)}")
    
    def serve_index(self, target_path: str = ""):
        """服务首页，支持路径参数"""
        try:
            # 注入路径参数到HTML中
            html_content = self.inject_path_parameter(self.html_content, target_path)
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html_content.encode('utf-8'))
        except Exception as e:
            self.log_error("服务首页时出错: %s", str(e))
            self.send_error(500, f"服务首页时出错: {str(e)}")
    
    def inject_path_parameter(self, html_content: str, path: str) -> str:
        """将路径参数注入到HTML中"""
        if not path:
            return html_content
        
        # 使用JavaScript变量注入路径参数
        script_injection = f'''
        <script>
            // 从URL参数注入的初始路径
            const initialPathFromURL = "{self.escape_js_string(path)}";
        </script>
        '''
        
        # 在head标签结束前注入
        return html_content.replace('</head>', f'{script_injection}</head>')
    
    def escape_js_string(self, s: str) -> str:
        """转义字符串用于JavaScript"""
        return s.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'").replace('\n', '\\n').replace('\r', '\\r')
    
    def serve_files_api(self, target_path: str = ""):
        """服务文件列表API"""
        try:
            files_data = self.scan_cdn_folder(target_path)
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(files_data, ensure_ascii=False).encode('utf-8'))
        except Exception as e:
            self.log_error("扫描文件夹时出错: %s", str(e))
            self.send_error(500, f"扫描文件夹时出错: {str(e)}")
    
    def serve_navigate_api(self, target_path: str = ""):
        """服务文件夹导航API"""
        try:
            navigation_data = self.get_navigation_data(target_path)
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(navigation_data, ensure_ascii=False).encode('utf-8'))
        except Exception as e:
            self.log_error("导航文件夹时出错: %s", str(e))
            self.send_error(500, f"导航文件夹时出错: {str(e)}")
    
    def serve_stats_api(self):
        """服务统计信息API"""
        try:
            stats = self.get_system_stats()
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(stats, ensure_ascii=False).encode('utf-8'))
        except Exception as e:
            self.log_error("获取统计信息时出错: %s", str(e))
            self.send_error(500, f"获取统计信息时出错: {str(e)}")
    
    def serve_file_download(self, path):
        """服务文件下载"""
        try:
            filename = path.replace('/download/', '')
            file_path = self.cdn_path / urllib.parse.unquote(filename)
            
            if not file_path.exists() or not file_path.is_file():
                self.send_error(404, "文件不存在")
                return
            
            # 设置下载头
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Disposition', f'attachment; filename="{file_path.name}"')
            self.send_header('Content-Length', str(file_path.stat().st_size))
            self.end_headers()
            
            # 发送文件内容
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
                
        except Exception as e:
            self.log_error("下载文件时出错: %s", str(e))
            self.send_error(500, f"下载文件时出错: {str(e)}")
    
    def scan_cdn_folder(self, relative_path: str = "") -> Dict[str, Any]:
        """扫描CDN文件夹"""
        target_path = self.cdn_path / relative_path if relative_path else self.cdn_path
        
        if not target_path.exists():
            return {
                "files": [], 
                "folders": [], 
                "folder_count": 0, 
                "file_count": 0, 
                "total_size": "0 B",
                "current_path": relative_path,
                "parent_path": self.get_parent_path(relative_path)
            }
        
        if not target_path.is_dir():
            return {
                "files": [], 
                "folders": [], 
                "folder_count": 0, 
                "file_count": 0, 
                "total_size": "0 B",
                "current_path": relative_path,
                "parent_path": self.get_parent_path(relative_path)
            }
        
        files_data = []
        folders_data = []
        total_size = 0
        folder_count = 0
        file_count = 0
        
        try:
            # 扫描文件和文件夹
            for item in target_path.iterdir():
                if item.is_file():
                    stat = item.stat()
                    file_info = {
                        "name": item.name,
                        "path": str(item.relative_to(self.cdn_path)),
                        "size": self.format_file_size(stat.st_size),
                        "size_bytes": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                        "type": self.get_file_type(item.name)
                    }
                    files_data.append(file_info)
                    total_size += stat.st_size
                    file_count += 1
                elif item.is_dir():
                    folder_info = {
                        "name": item.name,
                        "path": str(item.relative_to(self.cdn_path)),
                        "modified": datetime.fromtimestamp(item.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    }
                    folders_data.append(folder_info)
                    folder_count += 1
        
        except Exception as e:
            self.log_error("扫描文件夹时发生错误: %s", str(e))
        
        return {
            "files": sorted(files_data, key=lambda x: x["name"].lower()),
            "folders": sorted(folders_data, key=lambda x: x["name"].lower()),
            "folder_count": folder_count,
            "file_count": file_count,
            "total_size": self.format_file_size(total_size),
            "total_size_bytes": total_size,
            "current_path": relative_path,
            "parent_path": self.get_parent_path(relative_path)
        }
    
    def get_navigation_data(self, relative_path: str = "") -> Dict[str, Any]:
        """获取导航数据"""
        return self.scan_cdn_folder(relative_path)
    
    def get_parent_path(self, current_path: str) -> str:
        """获取父级路径"""
        if not current_path:
            return ""
        
        path_parts = current_path.split('/')
        if len(path_parts) <= 1:
            return ""
        
        return '/'.join(path_parts[:-1])
    
    def get_system_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        import platform
        import psutil
        
        try:
            # 获取系统信息
            system_info = {
                "platform": platform.system(),
                "platform_version": platform.version(),
                "processor": platform.processor(),
                "hostname": platform.node()
            }
            
            # 获取内存使用情况
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('.')
            
            # 获取服务器运行时间
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            
            return {
                "system": system_info,
                "memory": {
                    "total": self.format_file_size(memory.total),
                    "used": self.format_file_size(memory.used),
                    "percent": memory.percent
                },
                "disk": {
                    "total": self.format_file_size(disk.total),
                    "used": self.format_file_size(disk.used),
                    "percent": disk.percent
                },
                "uptime": str(uptime).split('.')[0]  # 去除微秒部分
            }
        except ImportError:
            return {"error": "需要psutil库来获取系统信息"}
        except Exception as e:
            return {"error": str(e)}
    
    def format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    def get_file_type(self, filename: str) -> str:
        """获取文件类型"""
        ext = Path(filename).suffix.lower()
        file_types = {
            '.jpg': 'image', '.jpeg': 'image', '.png': 'image', '.gif': 'image', '.bmp': 'image', '.webp': 'image',
            '.pdf': 'document', '.doc': 'document', '.docx': 'document', '.ppt': 'document', '.pptx': 'document',
            '.txt': 'text', '.md': 'text', '.json': 'text', '.xml': 'text', '.csv': 'text',
            '.zip': 'archive', '.rar': 'archive', '.7z': 'archive', '.tar': 'archive', '.gz': 'archive',
            '.mp4': 'video', '.avi': 'video', '.mkv': 'video', '.mov': 'video', '.wmv': 'video',
            '.mp3': 'audio', '.wav': 'audio', '.flac': 'audio', '.aac': 'audio', '.ogg': 'audio',
            '.exe': 'executable', '.msi': 'executable'
        }
        return file_types.get(ext, 'file')

def display_banner():
    """显示启动横幅"""
    if not HAS_RICH:
        print("\n" + "="*50)
        print("      ByUsiCDN - Index Fo 服务器")
        print("="*50)
        return
    
    banner_table = Table(show_header=False, show_edge=True, padding=(0, 2))
    banner_table.add_column(justify="center")
    
    banner_table.add_row("[bold red]╔═╗╦ ╦╦ ╔╦╗╔═╗╔╦╗╔═╗╦  ╔═╗[/bold red]")
    banner_table.add_row("[bold red]╠═╝║ ║║  ║ ║╣  ║ ╠═╣║  ║╣ [/bold red]")
    banner_table.add_row("[bold red]╩  ╚═╝╩═╝╩ ╚═╝ ╩ ╩ ╩╩═╝╚═╝[/bold red]")
    banner_table.add_row("")
    banner_table.add_row("[bold cyan]CDN 文件索引和分发系统[/bold cyan]")
    
    console.print(Panel(banner_table, style="bold red", padding=(1, 4)))
    
    # 显示配置信息
    info_table = Table.grid(padding=(0, 1))
    info_table.add_column(style="bold cyan", justify="right")
    info_table.add_column(style="white")
    
    info_table.add_row("访问地址:", f"http://{CONFIG['host']}:{CONFIG['port']}")
    info_table.add_row("数据文件夹:", str(Path(CONFIG['cdn_data_folder']).absolute()))
    info_table.add_row("主题颜色:", CONFIG['theme_color'])
    info_table.add_row("模糊效果:", CONFIG['blur_intensity'])
    
    console.print(Panel(info_table, title="📋 配置信息", border_style="cyan"))

def main():
    """主函数"""
    try:
        # 创建必要的文件夹
        cdn_path = Path(CONFIG["cdn_data_folder"])
        cdn_path.mkdir(exist_ok=True)
        
        # 检查HTML文件是否存在
        html_file = Path(CONFIG["html_file"])
        if not html_file.exists():
            console.print(f"\n[bold yellow]⚠️  警告: HTML文件 {CONFIG['html_file']} 不存在[/bold yellow]")
            console.print("[yellow]服务器将继续运行，但界面可能无法正常显示[/yellow]")
        
        # 显示启动横幅
        display_banner()
        
        # 设置自定义请求处理器
        handler = ByUsiCDNRequestHandler
        
        # 创建服务器
        with socketserver.TCPServer((CONFIG["host"], CONFIG["port"]), handler) as httpd:
            if HAS_RICH:
                console.print(f"\n🎉 [bold green]服务器启动成功![/bold green]")
                console.print(f"\n⏹️  [bold yellow]按 Ctrl+C 停止服务器[/bold yellow]\n")
            else:
                print(f"\n服务器启动成功!")
                print(f"按 Ctrl+C 停止服务器\n")
            
            # 启动服务器
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        if HAS_RICH:
            console.print(f"\n\n[bold yellow]👋 服务器已安全停止[/bold yellow]")
        else:
            print(f"\n\n服务器已安全停止")
    except Exception as e:
        if HAS_RICH:
            console.print(f"\n[bold red]❌ 启动服务器时出错: {e}[/bold red]")
        else:
            print(f"\n启动服务器时出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()