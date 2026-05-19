"""
打分式拆分类型分析 — 用序数可信度打分替代规则式推荐。
"""
import sys
from _type_patterns_config import build_type_patterns, iter_matches
from analyze_split_types import SPLIT_TYPES
from _protection_config import apply_protection_blocks
# ======================================================================
# 内嵌打分核心（原 score_ords.py，已合并）
# ======================================================================

BOUNDARY = 6.0

def _parse_ord(s):
    return tuple(int(p) for p in s.split('.'))

def _smaller(a, b):
    if len(a) != len(b): return len(a) < len(b)
    return a[-1] < b[-1]

def _bigger(a, b):
    return _smaller(b, a)

def _rel(a, b):
    """亲戚关系判断（内嵌自 score_ords.py）"""
    if a == b: return 0, 0
    # 兄弟：同前缀，末位差1
    if len(a) == len(b) and a[:-1] == b[:-1] and abs(a[-1] - b[-1]) == 1:
        return 1, 3.0
    # 父子：a 是 b 的父级
    if len(b) == len(a) + 1 and b[:-1] == a:
        return 2, 2.5
    if len(a) == len(b) + 1 and a[:-1] == b:
        return 2, 2.5
    # 叔侄：a 是 b 的叔叔（a 与 b 的父级是兄弟）
    if len(a) + 1 == len(b) and a[:-1] == b[:-2] and abs(a[-1] - b[-2]) == 1:
        return 4, 2.0
    if len(b) + 1 == len(a) and b[:-1] == a[:-2] and abs(b[-1] - a[-2]) == 1:
        return 4, 2.0
    # 祖孙
    if len(b) == len(a) + 2 and b[:-2] == a:
        return 3, 1.5
    if len(a) == len(b) + 2 and a[:-2] == b:
        return 3, 1.5
    # 祖孙（跨章）：1.1.1 → 2, 7.3.2 → 8
    if len(a) >= 3 and len(b) == 1 and a[0] + 1 == b[0]:
        return 3, 1.5
    if len(b) >= 3 and len(a) == 1 and b[0] + 1 == a[0]:
        return 3, 1.5
    # 标量兄弟
    if len(a) == 1 and len(b) == 1 and abs(a[0] - b[0]) == 1:
        return 1, 3.0
    # 广义爷孙/祖先：同前缀后深度差亲缘
    k = 0
    while k < min(len(a), len(b)) and a[k] == b[k]:
        k += 1
    if k > 0:
        ra = len(a) - k
        rb = len(b) - k
        dd = abs(ra - rb)
        if dd == 2:
            return 3, 1.5   # 爷孙（深度差2）
        if dd >= 3:
            return 5, max(1.5 - 0.25 * (dd - 2), 0.3)  # 祖先
    return 0, 0

def _connected(a, b):
    t, _ = _rel(a, b)
    if t < 1: return False
    if t == 4: return len(a) > len(b)
    if t == 3 and len(a) >= 3 and len(b) == 1: return True
    if t == 3:
        # 直接祖孙：短→长为前进
        if len(a) + 2 == len(b) and b[:-2] == a: return _smaller(a, b)
        if len(b) + 2 == len(a) and a[:-2] == b: return _smaller(a, b)
        # 广义爷孙：深→浅为前进
        return len(a) > len(b)
    if t == 5: return len(a) > len(b)  # 祖先
    return _smaller(a, b)

def score_ordinals(ords):
    """
    对 ordinals（str 列表）逐个打分，返回 (scores, kept_mask)。
    scores[i]: 每个序数的最终分数
    kept_mask[i]: True 表示保留（分数 >= 阈值）
    """
    n = len(ords)
    parsed = [_parse_ord(o) for o in ords]
    scores = [0.0] * n

    # Phase 0: 0值惩罚
    for i in range(n):
        if 0 in parsed[i]: scores[i] -= 5.0

    # Phase 1: 初始得分
    for i in range(n):
        for d in [1, 2]:
            if i - d >= 0:
                t, st = _rel(parsed[i], parsed[i-d])
                if t >= 1:
                    if _smaller(parsed[i-d], parsed[i]):
                        scores[i] += st * (1.0 - (d-1)*0.4)
                        scores[i-d] += st * (1.0 - (d-1)*0.4) * 0.5
                    else: scores[i] -= st * (1.0 - (d-1)*0.4)
            if i + d < n:
                t, st = _rel(parsed[i], parsed[i+d])
                if t >= 1:
                    if _bigger(parsed[i+d], parsed[i]):
                        scores[i] += st * (1.0 - (d-1)*0.4)
                        scores[i+d] += st * (1.0 - (d-1)*0.4) * 0.5
                    else: scores[i] -= st * (1.0 - (d-1)*0.4)

    # Phase 2: 能量传播
    for _ in range(3):
        ns = scores[:]
        for i in range(n):
            l, r = 0.0, 0.0
            for d in range(1, min(6, i+1)):
                j = i - d
                if scores[j] >= BOUNDARY: break
                t, st = _rel(parsed[i], parsed[j])
                if t >= 1:
                    x = sum(1 for k in range(j+1, i) if scores[k] < BOUNDARY)
                    if _smaller(parsed[j], parsed[i]):
                        l += st * (0.6**d) * (0.8**x)
                    else:
                        l -= st * (0.6**d) * (0.8**x)
            for d in range(1, min(6, n-i)):
                j = i + d
                if scores[j] >= BOUNDARY: break
                t, st = _rel(parsed[i], parsed[j])
                if t >= 1:
                    x = sum(1 for k in range(i+1, j) if scores[k] < BOUNDARY)
                    if _bigger(parsed[j], parsed[i]):
                        r += st * (0.6**d) * (0.8**x)
                    else:
                        r -= st * (0.6**d) * (0.8**x)
            ns[i] = scores[i] + l + r
        scores = ns

    # Phase 3: 连通链检测
    visited = [False] * n
    chain_reward = [0.0] * n     # 记录每人Phase 3链奖，供Phase 5回滚
    i = 0
    while i < n:
        if visited[i]: i += 1; continue
        members = [i]
        while True:
            found = False
            cur = members[-1]
            for skip in range(1, 5):
                nxt = cur + skip
                if nxt >= n: break
                if _connected(parsed[cur], parsed[nxt]) and all(scores[k] < BOUNDARY for k in range(cur+1, nxt)):
                    # 跳过中间元素时，若中间元素与目标可直接连接（性质更优），
                    # 则说明未入链的中间元素更应成为链成员，阻止远距跨越
                    blocked = False
                    for k in range(cur+1, nxt):
                        if _connected(parsed[k], parsed[nxt]):
                            blocked = True
                            break
                    if not blocked:
                        members.append(nxt); found = True; break
            if not found: break
        cl = len(members)
        if cl >= 3 and sum(scores[k] for k in members) > -cl:
            each = cl ** 1.4
            for k in members: scores[k] += each; visited[k] = True; chain_reward[k] += each
            i = members[-1] + 1
        else: visited[i] = True; i += 1

    # Phase 3.5: 纯噪声链抑制
    thr4 = 4.0
    i = 0
    while i < n:
        if scores[i] < thr4:
            j = i + 1
            while j < n and scores[j] < thr4: j += 1
            if j - i >= 3:
                has_c = False
                for k in range(i, j):
                    for d in range(1, 4):
                        if k-d>=0 and _connected(parsed[k], parsed[k-d]): has_c = True; break
                        if k+d<n and _connected(parsed[k], parsed[k+d]): has_c = True; break
                    if has_c: break
                if not has_c:
                    pen = (j-i) * 2.0
                    for k in range(i, j): scores[k] -= pen
            i = j
        else: i += 1

    # Phase 4: 亲戚挤压惩罚
    for i in range(n):
        if visited[i]: continue
        li = None
        for d in range(1, 6):
            if i-d >= 0 and visited[i-d]: li = i-d; break
        ri = None
        for d in range(1, 6):
            if i+d < n and visited[i+d]: ri = i+d; break
        if li is not None and ri is not None:
            t, _ = _rel(parsed[li], parsed[ri])
            if t >= 1:
                gap = ri - li
                av = (abs(scores[li]) + abs(scores[ri])) / 2
                scores[i] -= av * ((6 - gap) / 6) * 0.3

    threshold = 4.0  # 提前定义供 Phase 5 使用

    # Phase 5: 序列重置惩罚 — 相对链长扣分
    prev_len = 0
    prev_start_ord = None
    i = 0
    while i < n:
        chain = [i]
        while True:
            found = False
            for skip in range(1, 5):
                nxt = chain[-1] + skip
                if nxt >= n: break
                if _connected(parsed[chain[-1]], parsed[nxt]) \
                   and all(scores[k] < BOUNDARY for k in range(chain[-1]+1, nxt)):
                    chain.append(nxt); found = True; break
            if not found: break
        cl = len(chain)
        first_ord = parsed[chain[0]][0]
        extra = max(0, first_ord - 1) * 0.5

        # 非1开头且maxn<3的组/堆：极大扣分 + 吐回 chain_reward（不享受链长加分）
        if first_ord != 1 and cl < 3:
            extra += 5.0
            for idx in chain:
                scores[idx] -= chain_reward[idx]

        if cl >= 3:
            head_penalty = (prev_len - cl) * 0.5 - 1 + extra
            if scores[chain[0]] - head_penalty >= threshold:
                for pos, idx in enumerate(chain, 1):
                    penalty = (prev_len - cl) * 0.5 - pos + extra
                    scores[idx] -= penalty
                prev_len = cl
                prev_start_ord = first_ord
                i = chain[-1] + 1
            else:
                for idx in chain:
                    scores[idx] -= chain_reward[idx]
                scores[chain[0]] -= head_penalty
                i = chain[0] + 1
        else:
            # 短链：不计链长奖励和各类加分，清零后只保留扣分
            for idx in chain:
                scores[idx] = 0.0
            base_penalty = max(2.0, (prev_len - 1) * 0.8 - 1)
            # 非1开头短链：额外极大扣分
            if first_ord != 1:
                base_penalty += 5.0
            # 长1链(>=10)对周围零散元素的极大扣分压制
            if prev_start_ord == 1 and prev_len >= 10:
                base_penalty *= 3
            for idx in chain:
                scores[idx] -= base_penalty
            i = chain[-1] + 1

    kept = [s >= threshold for s in scores]
    return scores, kept


def analyze(text):
    """
    打分式拆分类型分析：保护块 → 全量匹配 → 去重 → 打分 → 推荐类型。
    返回与 print_report() 相同结构的 dict:
        {spine_types, satellite_types, all_tags, max_n, max_gc, is_plain, ...}
    """
    # 打分子集：与拆分引擎 global_backward_rollback + 条二次回卷 的序数入口一致
    SCORED_TYPES = {"条", "数字条", "数字点", "数字点点",
                    "数字直连中文", "数字空格", "数字节"}

    # 1. 保护块 → 全量匹配（一次过，不重复）
    protected, _ = apply_protection_blocks(text)
    patterns = build_type_patterns(SPLIT_TYPES)

    # 收集原始 matches（通过共享 iter_matches，过滤器与拆分引擎一致）
    all_raw = []
    for name, _pat, func, m in iter_matches(patterns, protected, type_names=SCORED_TYPES):
        try:
            val = func(m)
            if val is None:
                continue
            all_raw.append((name, m.group(), m.start(), m.end(), val))
        except Exception:
            continue

    # 2. 重叠区间去重（类型优先级：数字直连中文 > 数字点 > 其他）
    TYPE_PRIORITY = {"数字直连中文": 0, "数字点": 1, "数字点点": 1}
    all_raw.sort(key=lambda x: (x[2], TYPE_PRIORITY.get(x[0], 2), -len(x[1])))
    deduped = []
    occupied = []
    for item in all_raw:
        n, g, s, e, v = item
        if not any(s < oe and e > os for os, oe in occupied):
            occupied.append((s, e))
            deduped.append(item)

    # 3. 构建 ords 字符串列表 → 打分
    ords_str = []
    for _, _, _, _, v in deduped:
        if isinstance(v, tuple):
            ords_str.append('.'.join(str(x) for x in v))
        else:
            ords_str.append(str(v))

    scores, kept_mask = score_ordinals(ords_str)

    # 4. 按类型分组保留的序数
    kept_by_type = {}
    for i, keep in enumerate(kept_mask):
        if keep:
            tname = deduped[i][0]
            val = deduped[i][4]
            kept_by_type.setdefault(tname, []).append(val)

    # 5. 构建报告
    all_tags = list(kept_by_type.keys())

    spine_types = []
    max_n = 0
    for t in ["数字点", "数字点点"]:
        if t in kept_by_type:
            cnt = len(kept_by_type[t])
            if cnt > max_n:
                max_n = cnt
                spine_types = [t]

    satellite_types = []
    max_gc = 0
    for t in all_tags:
        if t not in spine_types:
            cnt = len(kept_by_type[t])
            if cnt > max_gc:
                max_gc = cnt
                satellite_types = [t]

    is_plain = not bool(all_tags)

    return {
        "spine_types": spine_types,
        "satellite_types": satellite_types,
        "all_tags": all_tags,
        "max_n": max_n,
        "max_gc": max_gc,
        "is_plain": is_plain,
        "char_count": len(text) if text else 0,
        "para_count": text.count('\n') + 1 if text else 0,
        "_scores": scores,
        "_kept_mask": kept_mask,
        "_ords": ords_str,
    }


# ======================================================================
#  入口 — 完全复刻流水线调用路径，保证终端与流水线打分一致
# ======================================================================
if __name__ == '__main__':
    import sys
    import os
    from importlib import util as _iu

    _HERE = os.path.dirname(os.path.abspath(__file__))

    _ps = _iu.spec_from_file_location(
        '_post', os.path.join(_HERE, 'post-类型拆分.py'))
    _pm = _iu.module_from_spec(_ps)
    _ps.loader.exec_module(_pm)
    clean_html = _pm.clean_html

    def _fetch_from_db(law_id):
        try:
            import pymysql
        except ImportError:
            print("pymysql 未安装，请执行 pip install pymysql")
            sys.exit(1)
        DB_CONFIG = {
            "host": "192.168.1.109",
            "port": 8001,
            "user": "xoops_root",
            "password": "654321",
            "database": "mtai_serv",
        }
        conn = pymysql.connect(**DB_CONFIG)
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT attachment_url FROM mt_kb_law_metadata WHERE law_id = %s",
                    (law_id,))
                res = cursor.fetchone()
                if not res or not res[0]:
                    print(f"未找到 law_id: {law_id}")
                    sys.exit(1)
                return res[0]
        finally:
            conn.close()

    if len(sys.argv) < 2:
        print("用法: python analyze_scored.py <文件路径>")
        print("      python analyze_scored.py --id <law_id>")
        sys.exit(1)

    if sys.argv[1] == "--id" and len(sys.argv) > 2:
        law_id = sys.argv[2]
        print(f"从数据库拉取 law_id={law_id} ...")
        raw_text = _fetch_from_db(law_id)
        text = clean_html(raw_text)
        text, _ = apply_protection_blocks(text)
        print(f"原始长度: {len(raw_text)} 字符, 清洗后: {len(text)} 字符")
    else:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            text = f.read()
        text = clean_html(text)
        text, _ = apply_protection_blocks(text)

    report = analyze(text)
    print(f"推荐类型: {report['all_tags']}")
    print(f"脊椎: {report['spine_types']} 附生: {report['satellite_types']}")
    total = sum(1 for k in report['_kept_mask'] if k)
    print(f"序数: {len(report['_ords'])} → 保留: {total}")
    for i, (o, kept, score) in enumerate(zip(report['_ords'], report['_kept_mask'], report['_scores']), start=1):
        flag = "✓" if kept else ""
        print(f"  {i:>4} {o:<12} {score:>8.1f}  | {flag}")