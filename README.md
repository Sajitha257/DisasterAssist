# Disaster Assist AI

An AI-powered disaster assistance chatbot that helps users understand what to do before, during, and after different emergency situations.

## About the Project

Disaster Assist AI is a web-based emergency information system designed to provide users with relevant disaster safety guidance.

The application combines Retrieval-Augmented Generation (RAG), BM25-based document retrieval, and Nova AI API integration to generate responses based on approved disaster safety information.

The goal is to make emergency guidance easier to access, understand, and use.

## Key Features

- Interactive chatbot interface.
- Disaster-related question answering.
- Before, during, and after disaster guidance.
- BM25-based information retrieval.
- RAG-based response generation.
- Nova AI API integration.
- Approved disaster safety information.
- Input validation and response checking.
- Automated test suite.

## Technologies Used

| Technology | Purpose |
|---|---|
| Python | Backend development |
| Gradio | Web interface |
| Nova AI API | AI-powered response generation |
| HTTPX | API communication |
| Rank-BM25 | Information retrieval |
| Python-dotenv | Environment variable management |
| Pytest | Automated testing |

## Project Structure

```text
DisasterAssist/
│
├── data/
│   └── approved/
│
├── src/
│   ├── chatbot/
│   ├── guide/
│   └── ui/
│
├── tests/
│
├── app.py
├── requirements.txt
├── pytest.ini
├── .env.example
├── .gitignore
└── README.md
```


## Installation and Setup

### 1. Clone the Repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
```

### 2. Open the Project Folder

```bash
cd DisasterAssist
```

### 3. Create a Virtual Environment

```bash
python -m venv .venv
```

### 4. Activate the Virtual Environment

**Windows PowerShell:**

```powershell
.\.venv\Scripts\Activate.ps1
```

### 5. Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### 6. Configure the API Key

Create a `.env` file in the project root directory.

Copy the contents of `.env.example` and provide your own Nova API configuration.

Example:

```env
NOVA_API_KEY=your_api_key_here
```

Use the exact environment variable name expected by your project code.

**Important:** Never upload your actual `.env` file or API key to GitHub.

### 7. Run the Application

```bash
python app.py
```

Open the local Gradio URL displayed in your terminal.

## Running Tests

Run the automated test suite using:

```bash
pytest -q
```

The project has previously achieved **1,345 passing tests** in the development environment. Results may vary after code or dependency changes.

## How It Works

1. The user submits a disaster-related question.
2. The system analyses the question.
3. Relevant approved information is retrieved using BM25.
4. The AI workflow uses the retrieved information to prepare a response.
5. Response validation checks the generated output.
6. The chatbot displays the response to the user.

## Safety Notice

Disaster Assist AI is intended to provide access to general disaster safety information.

It is not a replacement for emergency services, trained rescue personnel, or official government instructions. During an emergency, follow the directions of local authorities and contact emergency services when necessary.

## Future Enhancements

- Support for additional disaster categories.
- Improved multilingual assistance.
- Enhanced retrieval and response accuracy.
- Additional safety validation.
- Improved user interface and accessibility.
