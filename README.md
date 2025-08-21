# ZHTLLM - Local Meeting Assistant  

Hi, this is the **front end** of the project **ZHTLLM**.  
ZHTLLM is a **local meeting assistant** specially designed for the **AMD Ryzen AI platform**.  

---

## 🚀 How to Use  

Follow these steps to set up and run the project:  

---

### Step 1: Configure the environment with Conda  

Make sure you have [Anaconda](https://www.anaconda.com/download) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html) installed.  

Create the environment from the provided `environment.yml` file:  
```bash
conda env create -f environment.yml
```

Activate the environment:  
```bash
conda activate ZHTLLM
```

---

### Step 2: Launch the FastFlowLM (flm) server  

You can download **FastFlowLM** here:  
[https://github.com/FastFlowLM/FastFlowLM](https://github.com/FastFlowLM/FastFlowLM)  

Run the server in the terminal:  
```bash
flm serve
```

---

### Step 3: Launch the Ollama server  

(Assumption: you have already downloaded **Ollama**.)  

Change the Ollama's port to avoid conflict. Remember to set the same port in the software:  
```powershell
$env:OLLAMA_HOST="127.0.0.1:11500"
```

Run Ollama server:  
```bash
ollama serve
```

---

### Step 4: Navigate to the project folder  

```bash
cd C:\your-path\ZHTLLM
```

---

### Step 5: Run the GUI  

```bash
python main_gui_4.py
```

---

## ✅ Now you can use the software!  

## 📺 Showcase Video  

[![Watch the video](assets/cover.png)](https://www.bilibili.com/video/BV1xx411c7mD)  
  

---
