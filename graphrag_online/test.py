from pathlib import Path
from ZHTLLM_reasoning import run_build, run_search, RAG_ROOT
from ZHTLLM_online_build import initialize_project

# 项目初始化
def run_init():
    print("--- Init Started ---")
    initialize_project("test2", RAG_ROOT)


# 构建测试
def run_build_test():
    print("--- Running Build---")
    speaker_data = {
        " 说话人1 ": "3D-Speaker\Audio-Text/audio_2\snippet_1.wav",
        " 说话人2 ": "3D-Speaker\Audio-Text/audio_2/snippet_2.wav",
        " 说话人3 ": "3D-Speaker\Audio-Text/audio_2\snippet_3.wav",
    }
    run_build(
        name="test2",
        dialogue="3D-Speaker\Audio-Text/audio_2\combined.wav",
        speakers=speaker_data,
        text_files=["3D-Speaker\Audio-Text/audio_2/test.txt"],
        inference_mode="cloud",
        cloud_model="deepseek-chat",
        cloud_api_base="https://api.agicto.cn/v1",
        cloud_api_key="sk-ajs9XLA2QW1G6EbzolNq5OxOiKpkFjD7a5htM56HCrAGVHZF",
        # inference_mode="local",
        # local_model="llama3.2",
        # local_api_base="http://localhost:11434/v1/",
        embedding_model="nomic-embed-text",
        embedding_api_base="http://localhost:11500/api",
    )
    print("--- Build Finished ---\n")


# 本地查询
def run_local_query():
    """
    一个调用 local search 功能的示例。
    """
    print("--- Running Local Search ---")

    # 定义您要提出的问题
    query_text = "LLM在哪些领域有作用。"

    run_search(
        name="test2",
        query=query_text,
        method="local",  # 明确指定使用 'local' 搜索方法
        inference_mode="local",
        local_model="llama3.2",
        local_api_base="http://localhost:11434/v1/",
        embedding_model="nomic-embed-text",
        embedding_api_base="http://localhost:11500/api",
    )

    print("--- Search Finished ---")


# 在线查询
def run_online_query():
    print("--- Search Started ---")
    query_text = "LLM在哪些领域有作用。"

    run_search(
        name="test2",
        query=query_text,
        method="local",  # 明确指定使用 'local' 搜索方法
        inference_mode="cloud",
        cloud_model="deepseek-chat",
        cloud_api_base="https://api.agicto.cn/v1",
        cloud_api_key="sk-updTLk3DtUk5N2UrIIzD6yGgnE1WzmtXDlJGeTpaq6lucrSo",
        embedding_model="nomic-embed-text",
        embedding_api_base="http://localhost:11500/api",
    )


if __name__ == "__main__":
    #run_init()
    run_build_test()
    #run_online_query()

