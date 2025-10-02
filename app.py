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
    
    install_rich_traceback(show_locals=True)
    
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
    "port": 7060,
    "cdn_data_folder": "cdnData",
    "theme_color": "#FF0000",
    "blur_intensity": "25px",
    "site_title": "ByUsiCDN - Index Fo",
    "html_file": "index.html",
    "protected_paths": ["/api/secret", "/api/admin"]
}

class ByUsiCDNRequestHandler(http.server.SimpleHTTPRequestHandler):
    """ByUsiCDN自定义请求处理器"""
    
    def __init__(self, *args, **kwargs):
        self.cdn_path = Path(CONFIG["cdn_data_folder"])
        self.protected_paths = CONFIG["protected_paths"]
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
    <title>ByUsiCDN - Error</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 50px; text-align: center; }
        .error { color: #FF0000; background: #ffe6e6; padding: 20px; border-radius: 10px; }
    </style>
</head>
<body>
    <div class="error">
        <h1>⚠️ System Error</h1>
        <p>Cannot load interface template, please check if index.html file exists</p>
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
    
    def translate_path(self, path):
        """重写路径转换，将所有非API路径映射到 cdnData 目录"""
        # 解析路径
        path = urllib.parse.unquote(path)
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]
        
        # 检查是否是API路径
        if path.startswith('/api/'):
            # API路径不进行映射，返回不存在的路径
            return "/dev/null"
        
        # 特殊路径处理 - 根路径返回首页
        if path in ['/', '']:
            return str(Path.cwd() / CONFIG["html_file"])
        
        # 将URL路径映射到cdnData目录
        if path.startswith('/'):
            path = path[1:]
        
        # 构建实际文件路径
        file_path = self.cdn_path / path
        
        # 安全检查：确保路径在cdnData目录内
        try:
            file_path.resolve().relative_to(self.cdn_path.resolve())
        except ValueError:
            self.log_error("Path traversal attempt: %s", path)
            return "/dev/null"
        
        return str(file_path)
    
    def send_error_response(self, code, message):
        """发送错误响应，处理编码问题"""
        try:
            # 使用英文消息避免编码问题
            error_messages = {
                403: "Forbidden - Access Denied",
                404: "File Not Found", 
                500: "Internal Server Error"
            }
            english_message = error_messages.get(code, "Error")
            
            self.send_response(code)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            
            error_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Error {code}</title>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 50px; text-align: center; }}
                    .error {{ color: #FF0000; background: #ffe6e6; padding: 20px; border-radius: 10px; }}
                </style>
            </head>
            <body>
                <div class="error">
                    <h1>Error {code}</h1>
                    <p>{english_message}</p>
                    <p><small>{message}</small></p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(error_html.encode('utf-8'))
        except Exception as e:
            # 如果自定义错误也失败，使用原始方法
            super().send_error(code, english_message)
    
    def do_GET(self):
        """处理GET请求"""
        try:
            parsed_path = urllib.parse.urlparse(self.path)
            path = parsed_path.path
            query_params = urllib.parse.parse_qs(parsed_path.query)
            
            # 检查保护路径 - 只保护特定的API路径
            for protected_path in self.protected_paths:
                if path == protected_path:
                    self.send_error_response(403, "Protected directory access denied")
                    return
            
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
            elif path.startswith('/api/'):
                # 其他API路径返回404
                self.send_error_response(404, f"API endpoint not found: {path}")
            else:
                # 所有非API请求都映射到cdnData目录
                self.serve_cdn_file(path)
                
        except Exception as e:
            self.log_error("Request processing error: %s", str(e))
            self.send_error_response(500, f"Server error: {str(e)}")
    
    def serve_cdn_file(self, path):
        """服务CDN文件 - 直接映射到cdnData目录"""
        try:
            # 使用translate_path获取实际文件路径
            file_path = self.translate_path(path)
            
            # 检查文件是否存在
            if not os.path.exists(file_path) or file_path == "/dev/null":
                self.send_error_response(404, f"File not found: {path}")
                return
            
            # 如果是目录，返回文件列表页面
            if os.path.isdir(file_path):
                # 对于目录，我们返回首页，但注入路径参数
                relative_path = path[1:] if path.startswith('/') else path
                self.serve_index(relative_path)
                return
            
            # 确定MIME类型
            ext = os.path.splitext(file_path)[1].lower()
            mime_types = {
                '.txt': 'text/plain; charset=utf-8',
                '.html': 'text/html; charset=utf-8',
                '.htm': 'text/html; charset=utf-8',
                '.css': 'text/css; charset=utf-8',
                '.js': 'application/javascript; charset=utf-8',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.pdf': 'application/pdf',
                '.zip': 'application/zip',
                '.ico': 'image/x-icon',
                '.svg': 'image/svg+xml',
                '.json': 'application/json',
                '.xml': 'application/xml'
            }
            
            content_type = mime_types.get(ext, 'application/octet-stream')
            
            # 读取并发送文件
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            self.send_response(200)
            self.send_header('Content-type', content_type)
            self.send_header('Content-Length', str(len(file_data)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(file_data)
            
        except Exception as e:
            self.log_error("File serving error: %s", str(e))
            self.send_error_response(500, f"File serving error: {str(e)}")
    
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
            self.log_error("Index serving error: %s", str(e))
            self.send_error_response(500, f"Index serving error: {str(e)}")
    
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
            self.log_error("Folder scanning error: %s", str(e))
            self.send_error_response(500, f"Folder scanning error: {str(e)}")
    
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
            self.log_error("Navigation error: %s", str(e))
            self.send_error_response(500, f"Navigation error: {str(e)}")
    
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
            self.log_error("Stats error: %s", str(e))
            self.send_error_response(500, f"Stats error: {str(e)}")
    
    def serve_file_download(self, path):
        """服务文件下载"""
        try:
            filename = path.replace('/download/', '')
            file_path = self.cdn_path / urllib.parse.unquote(filename)
            
            # 安全检查
            try:
                file_path.resolve().relative_to(self.cdn_path.resolve())
            except ValueError:
                self.send_error_response(403, "Access denied")
                return
            
            if not file_path.exists() or not file_path.is_file():
                self.send_error_response(404, "File not found")
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
            self.log_error("Download error: %s", str(e))
            self.send_error_response(500, f"Download error: {str(e)}")
    
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
            self.log_error("Folder scanning error: %s", str(e))
        
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
        try:
            import psutil
            HAS_PSUTIL = True
        except ImportError:
            HAS_PSUTIL = False
        
        try:
            # 获取系统信息
            system_info = {
                "platform": platform.system(),
                "platform_version": platform.version(),
                "processor": platform.processor(),
                "hostname": platform.node()
            }
            
            stats = {
                "system": system_info,
                "uptime": "Unknown"
            }
            
            if HAS_PSUTIL:
                # 获取内存使用情况
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('.')
                
                # 获取服务器运行时间
                boot_time = datetime.fromtimestamp(psutil.boot_time())
                uptime = datetime.now() - boot_time
                
                stats.update({
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
                })
            else:
                stats["error"] = "psutil library required for full system info"
                
            return stats
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
        print("      ByUsiCDN - Index Fo Server")
        print("="*50)
        return
    
    banner_table = Table(show_header=False, show_edge=True, padding=(0, 2))
    banner_table.add_column(justify="center")
    
    banner_table.add_row("[bold red]╔═╗╦ ╦╦ ╔╦╗╔═╗╔╦╗╔═╗╦  ╔═╗[/bold red]")
    banner_table.add_row("[bold red]╠═╝║ ║║  ║ ║╣  ║ ╠═╣║  ║╣ [/bold red]")
    banner_table.add_row("[bold red]╩  ╚═╝╩═╝╩ ╚═╝ ╩ ╩ ╩╩═╝╚═╝[/bold red]")
    banner_table.add_row("")
    banner_table.add_row("[bold cyan]CDN File Index and Distribution System[/bold cyan]")
    
    console.print(Panel(banner_table, style="bold red", padding=(1, 4)))
    
    # 显示配置信息
    info_table = Table.grid(padding=(0, 1))
    info_table.add_column(style="bold cyan", justify="right")
    info_table.add_column(style="white")
    
    info_table.add_row("Access URL:", f"http://{CONFIG['host']}:{CONFIG['port']}")
    info_table.add_row("Data Folder:", str(Path(CONFIG['cdn_data_folder']).absolute()))
    info_table.add_row("CDN Mapping:", "All non-API paths → ./cdnData/")
    info_table.add_row("Protected Paths:", ", ".join(CONFIG['protected_paths']))
    info_table.add_row("Theme Color:", CONFIG['theme_color'])
    
    console.print(Panel(info_table, title="📋 Configuration Info", border_style="cyan"))

def main():
    """主函数"""
    try:
        # 创建必要的文件夹
        cdn_path = Path(CONFIG["cdn_data_folder"])
        cdn_path.mkdir(exist_ok=True)
        
        # 检查HTML文件是否存在
        html_file = Path(CONFIG["html_file"])
        if not html_file.exists():
            console.print(f"\n[bold yellow]⚠️  Warning: HTML file {CONFIG['html_file']} does not exist[/bold yellow]")
            console.print("[yellow]Server will continue running but interface may not display properly[/yellow]")
        
        # 显示启动横幅
        display_banner()
        
        # 设置自定义请求处理器
        handler = ByUsiCDNRequestHandler
        
        # 创建服务器
        with socketserver.TCPServer((CONFIG["host"], CONFIG["port"]), handler) as httpd:
            if HAS_RICH:
                console.print(f"\n🎉 [bold green]Server started successfully![/bold green]")
                console.print(f"\n📁 CDN File Access Examples:")
                console.print(f"   http://{CONFIG['host']}:{CONFIG['port']}/              → {cdn_path.absolute()}/")
                console.print(f"   http://{CONFIG['host']}:{CONFIG['port']}/file.txt      → {cdn_path.absolute()}/file.txt")
                console.print(f"   http://{CONFIG['host']}:{CONFIG['port']}/folder/       → {cdn_path.absolute()}/folder/")
                console.print(f"\n📊 API endpoints:")
                console.print(f"   http://{CONFIG['host']}:{CONFIG['port']}/api/files")
                console.print(f"   http://{CONFIG['host']}:{CONFIG['port']}/api/stats")
                console.print(f"\n⛔ Protected paths:")
                for path in CONFIG['protected_paths']:
                    console.print(f"   http://{CONFIG['host']}:{CONFIG['port']}{path}")
                console.print(f"\n⏹️  [bold yellow]Press Ctrl+C to stop server[/bold yellow]\n")
            else:
                print(f"\nServer started successfully!")
                print(f"CDN File Access Examples:")
                print(f"  http://{CONFIG['host']}:{CONFIG['port']}/ → {cdn_path.absolute()}/")
                print(f"Press Ctrl+C to stop server\n")
            
            # 启动服务器
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        if HAS_RICH:
            console.print(f"\n\n[bold yellow]👋 Server stopped safely[/bold yellow]")
        else:
            print(f"\n\nServer stopped safely")
    except Exception as e:
        if HAS_RICH:
            console.print(f"\n[bold red]❌ Server startup error: {e}[/bold red]")
        else:
            print(f"\nServer startup error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()