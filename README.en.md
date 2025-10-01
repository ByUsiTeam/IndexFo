# IndexFO Project Documentation

IndexFO is Python-based file indexing and CDN service management tool that provides an intuitive web interface for browsing and managing files on a server. It supports functionalities such as file browsing, uploading, downloading, navigation, and system status monitoring.

## Key Features

- **File Browsing**: View the file structure on the server through a web interface.
- **File Download**: Directly download files from the server.
- **File Upload**: Upload files to the server via a modal window.
- **System Status Monitoring**: Real-time display of memory and disk usage.
- **Responsive Design**: Supports access from both desktop and mobile devices.

## Technical Architecture

- **Backend**: An HTTP server written in Python (`app.py`), built on the `http.server` module.
- **Frontend**: A responsive interface built using HTML/CSS/JavaScript (`index.html`).
- **Functional Modules**:
  - File scanning and navigation data generation.
  - System resource statistics.
  - File type identification and size formatting.
  - API interface support for handling file operations.

## Installation and Execution

1. **Install Dependencies**:
   - Ensure Python 3.x is installed.
   - No additional libraries are required; the standard library is sufficient.

2. **Start the Service**:
   ```bash
   python app.py
   ```
   The service will be available by default at `http://localhost:8000`.

3. **Access the Interface**:
   Open your browser and navigate to `http://localhost:8000` to use the IndexFO web interface.

## Usage Instructions

- **Browse Files**: Navigate through directories and view file lists within the web interface.
- **Download Files**: Click on a file name to download the corresponding file.
- **Upload Files**: Click the upload button and select and upload files via the modal window.
- **View System Status**: Memory and disk usage are displayed on the right side of the interface.

## Contribution Guidelines

Contributions of code or suggestions are welcome! Please follow these steps:
1. Fork the project.
2. Create a new branch.
3. Submit a Pull Request.

## License

This project is licensed under the MIT License. For details, please refer to the LICENSE file in the project root directory.