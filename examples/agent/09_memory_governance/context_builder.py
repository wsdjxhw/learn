from models import UserMemory


def build_memory_context(memories: list[UserMemory]) -> str:
    # 只有通过治理过滤后的 active 且未过期记忆，才应该进入模型上下文。
    # 这一步把数据库对象转换成模型更容易理解的短文本。
    if not memories:
        return "本轮没有可使用的长期记忆。"

    lines = ["经过治理过滤后可使用的长期记忆："]
    for index, memory in enumerate(memories, start=1):
        expires_text = memory.expires_at.isoformat() if memory.expires_at else "不过期"
        lines.append(f"{index}. [{memory.memory_type}] {memory.key} = {memory.value}，过期时间：{expires_text}")
    return "\n".join(lines)
