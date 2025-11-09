<a name="readme-top"></a>

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]



<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/upskiller-xyz/server_lux">
    <img src="https://github.com/upskiller-xyz/DaylightFactor/blob/main/docs/images/logo_upskiller.png" alt="Logo" height="100" >
  </a>

  <h3 align="center">Lux Server</h3>

  <p align="center">
    Gateway server for daylight analysis, color management, and dataframe evaluation services
    <br />
    <a href="https://github.com/upskiller-xyz/server_lux">View Demo</a>
    ·
    <a href="https://github.com/upskiller-xyz/server_lux/issues">Report Bug</a>
    ·
    <a href="https://github.com/upskiller-xyz/server_lux/issues">Request Feature</a>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a>
        <li><a href="#api-endpoints">API Endpoints</a></li>
        <li><a href="#deployment">Deployment</a>
          <li><a href="#locally">Local deployment</a></li>
        </li>
    </li>
    <li><a href="#design">Design</a>
      <li><a href="#architecture">Architecture</a></li>
    </li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contribution">Contribution</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#trademark-notice">Trademark notice</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

The Daylight Server is a gateway service that orchestrates requests to remote microservices for:
- **Daylight Factor Analysis** - Process building images to estimate daylight distribution
- **Color Management** - Convert between numeric values and RGB color representations
- **Dataframe Evaluation** - Statistical analysis of daylight data
- **Room Encoding** - Convert room parameters to encoded PNG images for model input
- **Obstruction Analysis** - Calculate horizon and zenith obstruction angles

The server acts as a unified interface, handling multipart file uploads, forwarding requests to specialized remote services, and managing response orchestration.



<p align="right">(<a href="#readme-top">back to top</a>)</p>



### Built With

* [Python](https://www.python.org/)
* [Flask](https://flask.palletsprojects.com/)
* [Requests](https://requests.readthedocs.io/)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->
## Getting Started

To get a local copy up and running follow these simple steps.

### Prerequisites

* [Python 3.10+](https://www.python.org/downloads/)

### Installation

1. Clone the repo
   ```sh
   git clone https://github.com/upskiller-xyz/server_lux.git
   cd server_lux
   ```

2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```

3. Run the server:
   ```sh
   python src/main.py
   ```

   The server will start on `http://localhost:8081` by default.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- USAGE EXAMPLES -->
## Usage

### 🎯 Interactive Demo

**Start here!** For hands-on examples, see the **[Demo Notebook](example/demo.ipynb)**:

```bash
# Install Jupyter and start the demo
jupyter notebook example/demo.ipynb
```

### 🔧 API Endpoints

The server provides REST API endpoints for daylight analysis and color management:

#### Health Check
Check server status:

```python
import requests

response = requests.get("http://localhost:8081/")
print(response.json())
# Output: {"status": "running", "services": {...}}
```

#### get_df - Daylight Factor Analysis
Process building images with transformation parameters:

```python
import requests
import json

with open("building.png", "rb") as f:
    files = {"file": ("building.png", f)}
    response = requests.post(
        "http://localhost:8081/get_df",
        files=files,
        data={
            "translation": json.dumps({"x": 750, "y": 0}),
            "rotation": json.dumps([0])
        }
    )

result = response.json()
# Returns base64-encoded numpy array with daylight factor values
```

#### to_rgb - Convert Values to RGB
Convert numeric values to color representation:

```python
import requests
import numpy as np

values = np.random.rand(100, 100)  # Your numeric data
response = requests.post(
    "http://localhost:8081/to_rgb",
    json={"data": values.tolist(), "colorscale": "df"}
)

rgb_image = response.json()["data"]
```

#### to_values - Convert RGB to Values
Convert RGB colors back to numeric values:

```python
import requests
from PIL import Image
import numpy as np

img = np.array(Image.open("colored_result.png"))
response = requests.post(
    "http://localhost:8081/to_values",
    json={"data": img.tolist(), "colorscale": "df"}
)

values = response.json()["data"]
```

#### encode - Encode Room Parameters (Protected)
Convert room and window parameters to encoded PNG image:

```python
import requests

url = "http://localhost:8081/encode"
token = "your_api_token_here"  # Set via API_TOKEN env variable

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

payload = {
    "model_type": "df_default",
    "parameters": {
        "height_roof_over_floor": 2.7,
        "floor_height_above_terrain": 3.0,
        "room_polygon": [[0, 0], [5, 0], [5, 4], [0, 4]],
        "windows": {
            "main_window": {
                "x1": -0.6, "y1": 0.0, "z1": 0.9,
                "x2": 0.6, "y2": 0.0, "z2": 2.4,
                "window_sill_height": 0.9,
                "window_frame_ratio": 0.15,
                "window_height": 1.5,
                "obstruction_angle_horizon": 15.0,
                "obstruction_angle_zenith": 10.0
            }
        }
    }
}

response = requests.post(url, headers=headers, json=payload)

if response.status_code == 200:
    with open("encoded_room.png", "wb") as f:
        f.write(response.content)
    print("Image saved successfully!")
```

**Note:** This endpoint requires token authentication. Set the `API_TOKEN` environment variable on the server.

### Deployment

#### Local Development

Set up the server for local development and testing:

1. **Clone the Repository**
   ```bash
   git clone https://github.com/upskiller-xyz/server_lux.git
   cd server_lux
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set Environment Variables**
   ```bash
   export PORT=8081
   export API_TOKEN=your_secure_token_here  # Required for /encode endpoint
   export DEPLOYMENT_MODE=production  # Uses production GCP services
   ```

4. **Run the Server**
   ```bash
   python src/main.py
   ```
   The server will start on `http://localhost:8081` and connect to production microservices.

#### Docker Compose - Local Microservices Stack

Run the complete microservices stack locally with Docker Compose:

1. **Prerequisites**
   - [Docker](https://docs.docker.com/get-docker/)
   - [Docker Compose](https://docs.docker.com/compose/install/)

2. **Setup Environment**
   ```bash
   # Copy environment template
   cp .env.example .env

   # Edit .env and set your API token
   # DEPLOYMENT_MODE=local is already configured
   ```

3. **Authenticate with GCP**
   ```bash
   gcloud auth configure-docker europe-north2-docker.pkg.dev
   ```

4. **Pull Service Images**
   ```bash
   # Pull all microservice images from GCP Artifact Registry
   docker-compose pull
   ```

4. **Start All Services**
   ```bash
   docker-compose up -d
   ```

5. **Check Service Health**
   ```bash
   docker-compose ps
   ```

6. **View Logs**
   ```bash
   # All services
   docker-compose logs -f

   # Specific service
   docker-compose logs -f main
   ```

7. **Stop Services**
   ```bash
   docker-compose down
   ```

**Service Ports (Local):**
- Main Server: `http://localhost:8080`
- Color Management: `http://localhost:8001`
- Daylight Simulation: `http://localhost:8002`
- Metrics/Evaluation: `http://localhost:8003`
- Obstruction Calculation: `http://localhost:8004`
- Encoder: `http://localhost:8005`
- Postprocessing: `http://localhost:8006`

**Architecture:**
The Docker Compose setup creates an internal network where all services communicate using service names (e.g., `http://colormanage:8080`). The main server automatically detects `DEPLOYMENT_MODE=local` and routes requests to local services instead of GCP Cloud Run.

See [docs/deployment.md](docs/deployment.md) for detailed deployment documentation.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

#### Production Deployment (GCP Cloud Run)

For production deployment to Google Cloud Platform:

1. **Build and Push Docker Image**
   ```bash
   docker build -t gcr.io/YOUR_PROJECT/server-lux .
   docker push gcr.io/YOUR_PROJECT/server-lux
   ```

2. **Deploy to Cloud Run**
   ```bash
   gcloud run deploy server-lux \
     --image gcr.io/YOUR_PROJECT/server-lux \
     --platform managed \
     --region europe-north2 \
     --set-env-vars DEPLOYMENT_MODE=production,API_TOKEN=your_token
   ```

The server will automatically use production GCP service URLs when `DEPLOYMENT_MODE=production`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

#### Locally (Legacy)

Set up the Daylight Server locally for development and testing:

1. **Clone the Repository**
   ```bash
   git clone https://github.com/upskiller-xyz/server_lux.git
   cd server_lux
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set Environment Variables (Optional)**
   ```bash
   export PORT=8081
   export API_TOKEN=your_secure_token_here  # Required for /encode endpoint
   ```

4. **Run the Server**
   ```bash
   python src/main.py
   ```
   The server will start on `http://localhost:8081` by default.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- DESIGN -->
## Design

### Architecture

The Daylight Server follows object-oriented design principles with clean separation of concerns:

```
ServerApplication
├── HTTPClient (connection pooling, retries)
├── Remote Services
│   ├── ColorManageService
│   ├── DaylightService
│   ├── DFEvalService
│   ├── ObstructionService
│   └── EncoderService
├── OrchestrationService (multi-service workflows)
├── TokenAuthenticator (bearer token authentication)
└── EndpointController (request handling)
```



<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- ROADMAP -->
## Roadmap

See the [open issues](https://github.com/upskiller-xyz/server_lux/issues) for a full list of proposed features (and known issues).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTRIBUTION -->
## Contribution

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

**Development Guidelines:**

* Follow Object-Oriented Programming principles and design patterns (see [CLAUDE.md](CLAUDE.md))
* Use Enumerator pattern instead of magic strings
* Use Strategy pattern instead of if-else chains
* Implement proper inheritance hierarchies
* Add type hints to all functions
* Use structured logging (no print statements)

See [CLAUDE.md](CLAUDE.md) for detailed development instructions.

### Top contributors:

<a href="https://github.com/upskiller-xyz/server_lux/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=upskiller-xyz/server_lux" alt="Top Contributors" />
</a>

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- LICENSE -->
## License

See [License](./docs/LICENSE) for more details - or [read a summary](https://choosealicense.com/licenses/gpl-3.0/).

In short:

Strong copyleft. You **can** use, distribute and modify this code in both academic and commercial contexts. At the same time you **have to** keep the code open-source under the same license (`GPL-3.0`) and give the appropriate [attribution](#attribution) to the authors.

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Trademark Notice

- **"Upskiller"** is an informal collaborative name used by contributors affiliated with BIMTech Innovations AB.
- BIMTech Innovations AB owns all legal rights to the **Daylight Server** project.
- The GPL-3.0 license applies to code, not branding. Commercial use of the names requires permission.

Contact: [Upskiller](mailto:info@upskiller.xyz)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Contact

Stanislava Fedorova - [e-mail](mailto:stasya.fedorova@gmail.com)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

* [README template](https://github.com/othneildrew/Best-README-Template)
* [Flask](https://flask.palletsprojects.com/) - Web framework
* [Requests](https://requests.readthedocs.io/) - HTTP library
* Alberto Floris - [e-mail](mailto:alberto.floris@arkion.co)

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/upskiller-xyz/server_lux.svg?style=for-the-badge
[contributors-url]: https://github.com/upskiller-xyz/server_lux/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/upskiller-xyz/server_lux.svg?style=for-the-badge
[forks-url]: https://github.com/upskiller-xyz/server_lux/network/members
[stars-shield]: https://img.shields.io/github/stars/upskiller-xyz/server_lux.svg?style=for-the-badge
[stars-url]: https://github.com/upskiller-xyz/server_lux/stargazers
[issues-shield]: https://img.shields.io/github/issues/upskiller-xyz/server_lux.svg?style=for-the-badge
[issues-url]: https://github.com/upskiller-xyz/server_lux/issues
[license-shield]: https://img.shields.io/github/license/upskiller-xyz/server_lux.svg?style=for-the-badge
[license-url]: https://github.com/upskiller-xyz/server_lux/blob/master/docs/LICENSE.txt
