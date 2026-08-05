from models import UserMemory


def build_memory_context(memories: list[UserMemory]) -> str:
    # 上一模块学过上下文工程：模型每次调用前只能看到你放进去的内容。
    # 长期记忆要进入模型，也必须先被转换成清晰、短小、可控的上下文文本。
    if not memories:
        return "本轮没有检索到可复用的长期记忆。"

    lines = ["可复用的长期记忆："]
    for index, memory in enumerate(memories, start=1):
        lines.append(f"{index}. [{memory.memory_type}] {memory.key} = {memory.value}")
    return "\n".join(lines)
