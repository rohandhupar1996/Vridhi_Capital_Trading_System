"""
OAuth Callback Server for Zerodha Login
Automatically captures request_token from redirect URL
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional
import threading
import time
import queue


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback"""
    
    def __init__(self, *args, callback_queue=None, **kwargs):
        self.callback_queue = callback_queue
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET request (OAuth redirect)"""
        try:
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            # Extract request_token
            request_token = query_params.get('request_token', [None])[0]
            action = query_params.get('action', [None])[0]
            status = query_params.get('status', [None])[0]
            
            print(f"\n🔔 OAuth callback received! Path: {self.path}")
            print(f"   request_token: {request_token[:30] if request_token else 'None'}...")
            
            if request_token:
                # Success - put in queue
                if self.callback_queue:
                    self.callback_queue.put({
                        'request_token': request_token,
                        'status': 'success',
                        'action': action,
                        'status_param': status
                    })
                    print(f"✅ Token queued successfully")
                
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
                if self.callback_queue:
                    self.callback_queue.put({
                        'status': 'error',
                        'error': error or 'Unknown error'
                    })
                
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
        except Exception as e:
            print(f"❌ Error in callback handler: {e}")
            import traceback
            traceback.print_exc()
    
    def log_message(self, format, *args):
        """Log messages for debugging"""
        print(f"[Callback Server] {format % args}")


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
        self.callback_queue = queue.Queue()
        self._started = False
    
    def _create_handler(self):
        """Create handler with callback queue"""
        def handler(*args, **kwargs):
            return OAuthCallbackHandler(*args, callback_queue=self.callback_queue, **kwargs)
        return handler
    
    def start(self) -> bool:
        """Start the callback server"""
        try:
            self.server = HTTPServer(('localhost', self.port), self._create_handler())
            self.server.timeout = 1.0
            
            def run_server():
                print(f"[Callback Server] Starting server on port {self.port}...")
                while self._started:
                    try:
                        self.server.handle_request()
                    except Exception as e:
                        if self._started:
                            print(f"[Callback Server] Error: {e}")
            
            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self._started = True
            self.server_thread.start()
            # Give server a moment to start
            time.sleep(0.2)
            print(f"[Callback Server] Server started and listening on port {self.port}")
            return True
        except Exception as e:
            print(f"❌ Failed to start callback server: {e}")
            import traceback
            traceback.print_exc()
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
        last_progress_time = 0
        
        while time.time() - start_time < self.timeout:
            try:
                # Check queue with timeout
                callback_data = self.callback_queue.get(timeout=0.5)
                
                if callback_data:
                    status = callback_data.get('status')
                    if status == 'success':
                        request_token = callback_data.get('request_token')
                        if request_token:
                            print(f"\n✅ Request token received: {request_token[:30]}...")
                            return request_token
                        else:
                            print("⚠️  Callback received but no request_token found")
                    elif status == 'error':
                        error = callback_data.get('error', 'Unknown error')
                        print(f"\n❌ OAuth callback error: {error}")
                        raise Exception(f"OAuth callback error: {error}")
            except queue.Empty:
                # No callback yet, show progress
                elapsed = time.time() - start_time
                if elapsed - last_progress_time >= 5:
                    print(f"⏳ Still waiting for callback... ({int(elapsed)}s elapsed)")
                    last_progress_time = elapsed
                continue
        
        # Timeout
        elapsed = time.time() - start_time
        print(f"\n⏱️  OAuth callback timeout after {int(elapsed)}s")
        return None
    
    def get_callback_url(self) -> str:
        """Get the callback URL for Zerodha OAuth"""
        return f"http://localhost:{self.port}"

