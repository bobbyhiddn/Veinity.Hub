from flask import Flask
from dotenv import load_dotenv
import os
from hub.core import VeinityHub
from modules.aggregator.core import VeinityAggregator

# Load environment variables
load_dotenv()

def create_app():
    """Initialize and configure the Veinity application"""
    # Initialize components
    hub = VeinityHub()
    aggregator = VeinityAggregator()
    
    # Set up routes
    hub.setup_routes()
    aggregator.setup_routes()
    
    return hub.app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv('PORT', 8888))
    app.run(host='0.0.0.0', port=port)