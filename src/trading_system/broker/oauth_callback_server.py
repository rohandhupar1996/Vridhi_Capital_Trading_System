"""
OAuth Callback Server for Zerodha Login
Automatically captures request_token from redirect URL
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional
import threading
import time


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback"""
    
    def __init__(self, *args, callback_data=None, **kwargs):
        self.callback_data = callback_data
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET request (OAuth redirect)"""
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)
        
        # Extract request_token
        request_token = query_params.get('request_token', [None])[0]
        action = query_params.get('action', [None])[0]
        status = query_params.get('status', [None])[0]
        
        if request_token:
            # Success - store token
            if self.callback_data:
                self.callback_data['request_token'] = request_token
                self.callback_data['status'] = 'success'
                self.callback_data['action'] = action
                self.callback_data['status_param'] = status
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = """
            <html>
            <head><title>Login Successful</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1 style="color: green;">Login Successful!</h1>
                <p>You can close this window now.</p>
                <p style="color: gray; font-size: 12px;">The request token has been captured automatically.</p>
            </body>
            </html>
            """
            self.wfile.write(html.encode('utf-8'))
        else:
            # Error or no token
            error = query_params.get('error', [None])[0]
            if self.callback_data:
                self.callback_data['status'] = 'error'
                self.callback_data['error'] = error or 'Unknown error'
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = """
            <html>
            <head><title>Login Failed</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1 style="color: red;">Login Failed</h1>
            </body>
            </html>
            """
            self.wfile.write(html.encode('utf-8'))
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


class OAuthCallbackServer:
    """
    Local HTTP server to capture OAuth callback
    Automatically extracts request_token from redirect URL
    """
    
    def __init__(self, port: int = 8080, timeout: int = 120):
        self.port = port
        self.timeout = timeout
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.callback_data = {}
        self._started = False
    
    def _create_handler(self):
        """Create handler with callback data"""
        def handler(*args, **kwargs):
            return OAuthCallbackHandler(*args, callback_data=self.callback_data, **kwargs)
        return handler
    
    def start(self) -> bool:
        """Start the callback server"""
        try:
            self.server = HTTPServer(('localhost', self.port), self._create_handler())
            self.server.timeout = 1  # Check for shutdown every second
            
            def run_server():
                while self._started:
                    self.server.handle_request()
            
            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self._started = True
            self.server_thread.start()
            return True
        except Exception as e:
            print(f"Failed to start callback server: {e}")
            return False
    
    def stop(self):
        """Stop the callback server"""
        self._started = False
        if self.server:
            # Make a dummy request to wake up the server
            try:
                import urllib.request
                urllib.request.urlopen(f'http://localhost:{self.port}/stop', timeout=0.1)
            except:
                pass
    
    def wait_for_callback(self) -> Optional[str]:
        """
        Wait for OAuth callback and return request_token
        
        Returns:
            request_token if successful, None otherwise
        """
        if not self._started:
            if not self.start():
                return None
        
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            if 'status' in self.callback_data:
                if self.callback_data['status'] == 'success':
                    return self.callback_data.get('request_token')
                elif self.callback_data['status'] == 'error':
                    error = self.callback_data.get('error', 'Unknown error')
                    raise Exception(f"OAuth callback error: {error}")
            
            time.sleep(0.1)
        
        # Timeout
        return None
    
    def get_callback_url(self) -> str:
        """Get the callback URL for Zerodha OAuth"""
        return f"http://localhost:{self.port}"

