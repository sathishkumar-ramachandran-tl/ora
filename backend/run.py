import os

from dotenv import load_dotenv
load_dotenv()  # load .env before any app code reads os.environ

from app import create_app

app = create_app()

if __name__ == '__main__':
    # Default changed from 5000: macOS's AirPlay Receiver (ControlCenter) squats on
    # port 5000 by default, silently swallowing requests without Flask ever binding.
    port = int(os.environ.get('PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=False)
