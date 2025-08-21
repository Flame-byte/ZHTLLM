# ZHTLLM - Local Meeting Assistant  

Hi, this is the **front end** of the project **ZHTLLM**.  
ZHTLLM is a **local meeting assistant** specially designed for the **AMD Ryzen AI platform**.  

---

## 🚀 How to Use  

Follow these steps to set up and run the project:  

### Step 1: Launch the FastFlowLM (flm) server  

You can download **FastFlowLM** here:  
[https://github.com/FastFlowLM/FastFlowLM](https://github.com/FastFlowLM/FastFlowLM)  

Run the server in the terminal:  
```bash
flm serve
```

---

### Step 2: Launch the Ollama server  

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

### Step 3: Navigate to the project folder  

```bash
cd C:\your-path\ZHTLLM
```

---

### Step 4: Run the GUI  

```bash
python main_gui_v4.py
```

---

## ✅ Now you can use the software!  

## 📺 Showcase Video  

[![Watch the video](https://i0.hdslb.com/bfs/archive/YOUR_COVER_IMAGE.jpg)](https://www.bilibili.com/video/YOUR_BVID)  


---
