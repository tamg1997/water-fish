import asyncio, json, random, string, os, http.server, threading
from websockets.asyncio.server import serve

SUITS = ["S", "H", "C", "D"]
SUIT_RANK = {"S": 4, "H": 3, "C": 2, "D": 1}
RANKS = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
RANK_VALUE = {"A":1,"2":2,"3":3,"4":4,"5":5,"6":6,"7":7,"8":8,"9":9,"10":10,"J":10,"Q":10,"K":10}
RANK_ORDER = {"A":14,"K":13,"Q":12,"J":11,"10":10,"9":9,"8":8,"7":7,"6":6,"5":5,"4":4,"3":3,"2":2}

def make_deck():
    return [{"rank": r, "suit": s} for r in RANKS for s in SUITS]

def calc_group(rank1, suit1, rank2, suit2):
    v1, v2 = RANK_VALUE[rank1], RANK_VALUE[rank2]
    point = (v1 + v2) % 10
    is_pair = (rank1 == rank2)
    pair_rank = RANK_ORDER[rank1] if is_pair else 0
    if RANK_ORDER[rank1] >= RANK_ORDER[rank2]:
        max_rank, max_suit = RANK_ORDER[rank1], SUIT_RANK[suit1]
    else:
        max_rank, max_suit = RANK_ORDER[rank2], SUIT_RANK[suit2]
    return point, is_pair, pair_rank, max_rank, max_suit

def get_hand_type(cards):
    g1 = calc_group(cards[0]["rank"], cards[0]["suit"], cards[1]["rank"], cards[1]["suit"])
    g2 = calc_group(cards[2]["rank"], cards[2]["suit"], cards[3]["rank"], cards[3]["suit"])

    def stronger(a, b):
        pa, ia, pra, _, _ = a
        pb, ib, prb, _, _ = b
        if ia and not ib: return True
        if ib and not ia: return False
        if ia and ib: return pra >= prb
        if pa != pb: return pa >= pb
        ma, mb = a[3], b[3]
        if ma != mb: return ma >= mb
        return a[4] >= b[4]

    if not stronger(g1, g2):
        g1, g2 = g2, g1

    p1, pair1, prank1, mr1, ms1 = g1
    p2, pair2, prank2, mr2, ms2 = g2

    is_supreme = all(c["rank"] == cards[0]["rank"] for c in cards)
    is_water_fish = pair1 and pair2 and not is_supreme
    is_single_pair = (pair1 and not pair2) or (pair2 and not pair1)
    is_double_zero = p1 == 0 and p2 == 0 and not is_supreme
    rs = set(c["rank"] for c in cards)
    is_four_big = rs == {"10","J","Q","K"}

    return {
        "g1": {"point": p1, "is_pair": pair1, "pair_rank": prank1, "max_rank": mr1, "max_suit": ms1},
        "g2": {"point": p2, "is_pair": pair2, "pair_rank": prank2, "max_rank": mr2, "max_suit": ms2},
        "is_wulong": False, "is_supreme": is_supreme, "is_water_fish": is_water_fish,
        "is_single_pair": is_single_pair, "is_double_zero": is_double_zero, "is_four_big": is_four_big
    }

def compare_groups(g1, g2):
    if g1["is_pair"] and not g2["is_pair"]: return 1
    if g2["is_pair"] and not g1["is_pair"]: return -1
    if g1["is_pair"] and g2["is_pair"]:
        if g1["pair_rank"] > g2["pair_rank"]: return 1
        if g1["pair_rank"] < g2["pair_rank"]: return -1
        return 0
    if g1["point"] > g2["point"]: return 1
    if g1["point"] < g2["point"]: return -1
    if g1["max_rank"] > g2["max_rank"]: return 1
    if g1["max_rank"] < g2["max_rank"]: return -1
    if g1["max_suit"] > g2["max_suit"]: return 1
    if g1["max_suit"] < g2["max_suit"]: return -1
    return 0

def get_hand_display(ht):
    if ht["is_supreme"]: return "至尊水鱼"
    if ht["is_water_fish"]: return "水鱼"
    if ht["is_double_zero"]: return "双麻麻"
    if ht["is_four_big"]: return "四大麻"
    if ht["is_single_pair"]: return "单对子"
    return "普通点数"

def ai_best_grouping(cards):
    best, best_score = None, -1
    for i in range(4):
        for j in range(i+1, 4):
            tail_idx = [x for x in range(4) if x not in (i, j)]
            hc = [cards[i], cards[j]]
            tc = [cards[tail_idx[0]], cards[tail_idx[1]]]
            ht = get_hand_type(hc + tc)
            score = 0
            if ht["is_supreme"]: score = 500 + ht["g1"]["pair_rank"]
            elif ht["is_water_fish"]: score = 400 + ht["g1"]["pair_rank"] + ht["g2"]["pair_rank"]
            elif ht["is_double_zero"]: score = 50
            elif ht["is_single_pair"]: score = 300 + ht["g1"]["pair_rank"] + ht["g2"]["point"]
            else: score = ht["g1"]["point"] * 10 + ht["g2"]["point"]
            if score > best_score:
                best_score = score
                best = ([i, j], hc, tc, ht)
    if not best:
        hc, tc = [cards[0], cards[1]], [cards[2], cards[3]]
        ht = get_hand_type(hc + tc)
        best = ([0, 1], hc, tc, ht)
    return best

def ai_choose_action(ht):
    if ht["is_supreme"] or ht["is_water_fish"]: return "force"
    if ht["is_single_pair"]:
        r = random.random()
        if r < 0.4: return "dark"
        if r < 0.8: return "force"
        return "attack"
    g1p, g2p = ht["g1"]["point"], ht["g2"]["point"]
    if g1p >= 8 and g2p >= 5: return "dark" if random.random() < 0.4 else "force"
    if g1p <= 3 and g2p <= 2: return "walk"
    if ht["is_double_zero"]: return "walk"
    return "attack"

class Room:
    def __init__(self, code):
        self.code = code
        self.players = {}
        self.dealer_pid = None
        self.state = "waiting"
        self.order = []
        self.deck = []
        self.hands = {}
        self.groupings = {}
        self.actions = {}
        self.results = []
        self.drink_count = {}
        self.four_big_enabled = False

    def add_player(self, ws, name, pid, is_ai=False):
        self.players[pid] = {"ws": ws, "name": name, "is_ai": is_ai}
        self.order.append(pid)
        self.drink_count[pid] = 0

    def remove_player(self, pid):
        if pid in self.players: del self.players[pid]
        if pid in self.order: self.order.remove(pid)
        if self.dealer_pid == pid: self.dealer_pid = None

    async def broadcast(self, msg, exclude=None):
        dead = []
        for pid, p in list(self.players.items()):
            if pid == exclude: continue
            try:
                if not p.get("is_ai") and p["ws"]:
                    await p["ws"].send(json.dumps(msg, ensure_ascii=False))
            except:
                dead.append(pid)
        for pid in dead:
            self.remove_player(pid)

    async def send(self, pid, msg):
        if pid in self.players and not self.players[pid].get("is_ai") and self.players[pid]["ws"]:
            try:
                await self.players[pid]["ws"].send(json.dumps(msg, ensure_ascii=False))
            except:
                self.remove_player(pid)

    async def send_state_to_all(self):
        for pid in self.players:
            await self.send(pid, self.get_state(pid))

    def get_state(self, pid):
        base = {
            "type": "state",
            "room_code": self.code,
            "state": self.state,
            "players": [{
                "id": p, "name": self.players[p]["name"],
                "drinks": self.drink_count.get(p, 0),
                "is_dealer": p == self.dealer_pid,
                "is_ai": self.players[p].get("is_ai", False)
            } for p in self.order if p in self.players],
            "dealer_name": self.players[self.dealer_pid]["name"] if self.dealer_pid and self.dealer_pid in self.players else "",
            "you_are_dealer": pid == self.dealer_pid
        }
        if self.state in ("action", "comparing", "result") and pid in self.hands:
            base["your_cards"] = self.hands[pid]
        if self.state == "result":
            base["all_cards"] = getattr(self, "all_cards", {})
            base["results"] = self.results
        return base

rooms = {}
players_room = {}

def gen_code():
    while True:
        code = "".join(random.choices(string.digits, k=4))
        if code not in rooms: return code

async def check_and_resolve(room):
    idle = [p for p in room.order if p in room.players and p != room.dealer_pid
            and p not in room.actions and not any(r.get("player") == p for r in room.results)]
    if not idle:
        await resolve_round(room)

async def resolve_round(room):
    room.state = "comparing"
    dp = room.dealer_pid
    for p in room.order:
        if p not in room.players or p == dp: continue
        act = room.actions.get(p, "attack")
        pt = room.groupings.get(p, {}).get("hand_type", {})
        dt = room.groupings.get(dp, {}).get("hand_type", {})

        if pt.get("is_wulong"):
            room.results.append({"player": p, "player_name": room.players[p]["name"], "result": "wulong_loss", "drinks": 1, "desc": "乌龙摆反"})
            room.drink_count[p] += 1; continue
        if dt.get("is_wulong"):
            room.results.append({"player": p, "player_name": room.players[p]["name"], "result": "wulong_win", "drinks": 0, "dealer_drinks": 1, "desc": "庄家乌龙"})
            room.drink_count[dp] += 1; continue

        r1 = compare_groups(pt["g1"], dt["g1"])
        r2 = compare_groups(pt["g2"], dt["g2"])

        mult = 1
        if act in ("dark", "force"): mult = max(mult, 2)
        if pt["is_water_fish"]: mult = max(mult, 2)
        if pt["is_supreme"]: mult = max(mult, 3)
        if dt["is_water_fish"]: mult = max(mult, 2)
        if dt["is_supreme"]: mult = max(mult, 3)

        player_special = pt["is_double_zero"] and dt["is_water_fish"] and not dt["is_supreme"]
        dealer_special = dt["is_double_zero"] and pt["is_water_fish"] and not pt["is_supreme"]

        if player_special:
            room.drink_count[dp] += max(mult, 2)
            room.results.append({"player": p, "player_name": room.players[p]["name"], "result": "double_zero_win", "dealer_drinks": max(mult, 2), "desc": "双麻麻反杀水鱼"})
        elif dealer_special:
            room.drink_count[p] += max(mult, 2)
            room.results.append({"player": p, "player_name": room.players[p]["name"], "result": "double_zero_lose", "drinks": max(mult, 2), "desc": "庄家双麻麻反杀"})
        elif r1 == 1 and r2 == 1:
            room.drink_count[dp] += mult
            room.results.append({"player": p, "player_name": room.players[p]["name"], "result": "win", "dealer_drinks": mult})
        elif r1 == -1 and r2 == -1:
            room.drink_count[p] += mult
            room.results.append({"player": p, "player_name": room.players[p]["name"], "result": "lose", "drinks": mult})
        else:
            room.results.append({"player": p, "player_name": room.players[p]["name"], "result": "tie"})

    room.all_cards = {}
    for p in room.order:
        if p in room.players and p in room.groupings:
            g = room.groupings[p]
            room.all_cards[p] = {
                "name": room.players[p]["name"],
                "head": g["head"], "tail": g["tail"],
                "display": get_hand_display(g["hand_type"]),
                "is_dealer": p == dp
            }

    room.state = "result"
    await room.send_state_to_all()

    if room.order:
        idx = room.order.index(dp) if dp in room.order else -1
        next_idx = (idx + 1) % len(room.order)
        room.dealer_pid = room.order[next_idx]
    room.groupings = {}; room.actions = {}; room.hands = {}; room.results = []

async def ai_auto(room, ai_pid):
    await asyncio.sleep(0.8)
    if room.state != "grouping" or ai_pid not in room.hands: return
    cards = room.hands[ai_pid]
    _, hc, tc, ht = ai_best_grouping(cards)
    room.groupings[ai_pid] = {"head": hc, "tail": tc, "hand_type": ht}
    await room.broadcast({"type": "ai_grouped", "pid": ai_pid, "name": room.players[ai_pid]["name"]})

    if all(p in room.groupings for p in room.order if p in room.players):
        room.state = "action"
        await room.send_state_to_all()
        for p in room.order:
            if p in room.players and p != room.dealer_pid and not room.players[p].get("is_ai"):
                await room.send(p, {"type": "choose_action"})
        for p in room.order:
            if p in room.players and room.players[p].get("is_ai") and p != room.dealer_pid:
                act = ai_choose_action(room.groupings[p]["hand_type"])
                room.actions[p] = act
                await room.broadcast({"type": "ai_action", "pid": p, "name": room.players[p]["name"], "action": act})
                if act == "force":
                    await room.send(room.dealer_pid, {"type": "force_reveal", "from": room.players[p]["name"], "card": room.hands[p][0]})
        await check_and_resolve(room)

async def ws_handler(ws):
    pid = str(id(ws))
    room = None
    try:
        async for raw in ws:
            msg = json.loads(raw)
            act = msg.get("action", "")

            if act == "create":
                name = (msg.get("name", "") or "玩家").strip()[:8] or "玩家"
                code = gen_code()
                room = Room(code)
                rooms[code] = room
                room.add_player(ws, name, pid)
                room.dealer_pid = pid
                players_room[pid] = code
                room.four_big_enabled = msg.get("four_big", False)
                await room.send(pid, {"type": "created", "room_code": code})
                await room.send_state_to_all()

            elif act == "join":
                name = (msg.get("name", "") or "玩家").strip()[:8] or "玩家"
                code = msg.get("code", "").strip()
                if code not in rooms:
                    await ws.send(json.dumps({"type": "error", "msg": "房间不存在"}, ensure_ascii=False))
                    continue
                room = rooms[code]
                if len(room.players) >= 7:
                    await ws.send(json.dumps({"type": "error", "msg": "房间已满"}, ensure_ascii=False))
                    continue
                room.add_player(ws, name, pid)
                players_room[pid] = code
                await room.send(pid, {"type": "joined", "room_code": code})
                await room.send_state_to_all()

            elif act == "start":
                code = players_room.get(pid, "")
                if code not in rooms: continue
                room = rooms[code]
                if pid != room.dealer_pid: continue
                if len(room.players) < 2: continue
                room.state = "dealing"
                room.deck = make_deck()
                random.shuffle(room.deck)
                room.hands = {}; room.groupings = {}; room.actions = {}; room.results = []
                di = 0
                for p in room.order:
                    if p in room.players:
                        room.hands[p] = room.deck[di:di+4]
                        di += 4
                dn = room.players[room.dealer_pid]["name"]
                for p in room.players:
                    if not room.players[p].get("is_ai"):
                        await room.send(p, {"type": "dealt", "cards": room.hands.get(p, []), "dealer_name": dn})
                room.state = "grouping"
                await room.send_state_to_all()
                for p in room.order:
                    if p in room.players and room.players[p].get("is_ai") and p in room.hands:
                        asyncio.ensure_future(ai_auto(room, p))

            elif act == "group":
                code = players_room.get(pid, "")
                if code not in rooms: continue
                room = rooms[code]
                if room.state != "grouping": continue
                head_idx = msg.get("head", [])
                if len(head_idx) != 2: continue
                cards = room.hands.get(pid, [])
                if len(cards) != 4: continue
                tail_idx = [i for i in range(4) if i not in head_idx]
                hc = [cards[i] for i in head_idx]
                tc = [cards[i] for i in tail_idx]
                ht = get_hand_type(hc + tc)
                room.groupings[pid] = {"head": hc, "tail": tc, "hand_type": ht}
                await room.send(pid, {
                    "type": "grouped", "display": get_hand_display(ht),
                    "head": hc, "tail": tc, "wulong": ht["is_wulong"],
                    "g1": ht["g1"], "g2": ht["g2"]
                })
                if all(p in room.groupings for p in room.order if p in room.players):
                    room.state = "action"
                    await room.send_state_to_all()
                    for p in room.order:
                        if p in room.players and p != room.dealer_pid and not room.players[p].get("is_ai"):
                            await room.send(p, {"type": "choose_action"})
                    for p in room.order:
                        if p in room.players and room.players[p].get("is_ai") and p != room.dealer_pid:
                            act = ai_choose_action(room.groupings[p]["hand_type"])
                            room.actions[p] = act
                            await room.broadcast({"type": "ai_action", "pid": p, "name": room.players[p]["name"], "action": act})
                    await check_and_resolve(room)

            elif act == "action":
                code = players_room.get(pid, "")
                if code not in rooms: continue
                room = rooms[code]
                if room.state != "action" or pid == room.dealer_pid: continue
                choice = msg.get("choice", "")
                if choice not in ("walk", "attack", "dark", "force"): continue
                room.actions[pid] = choice
                if choice == "force":
                    reveal_idx = msg.get("reveal", 0)
                    cards = room.hands.get(pid, [])
                    card = cards[reveal_idx] if reveal_idx < len(cards) else cards[0]
                    await room.send(room.dealer_pid, {"type": "force_reveal", "from": room.players[pid]["name"], "card": card})
                    await room.send(pid, {"type": "action_done", "action": "强攻"})
                elif choice == "walk":
                    await room.send(room.dealer_pid, {"type": "walk_request", "from": room.players[pid]["name"]})
                    await room.send(pid, {"type": "action_done", "action": "走水", "waiting_dealer": True})
                elif choice == "dark":
                    await room.send(pid, {"type": "action_done", "action": "暗攻"})
                else:
                    await room.send(pid, {"type": "action_done", "action": "明攻"})
                await check_and_resolve(room)

            elif act == "dealer_respond":
                code = players_room.get(pid, "")
                if code not in rooms: continue
                room = rooms[code]
                if pid != room.dealer_pid: continue
                resp = msg.get("response", "")
                target = msg.get("target", "")
                if resp == "accept_walk":
                    room.results.append({"player": target, "player_name": room.players[target]["name"], "result": "walk", "drinks": 0})
                    await room.send(target, {"type": "walk_accepted"})
                    await check_and_resolve(room)
                elif resp == "reject_walk":
                    room.actions[target] = "attack"
                    await room.send(target, {"type": "walk_rejected"})
                    await check_and_resolve(room)
                elif resp == "accept_dark":
                    room.drink_count[room.dealer_pid] += 1
                    room.results.append({"player": target, "player_name": room.players[target]["name"], "result": "dealer_surrender", "dealer_drinks": 1})
                    await room.broadcast({"type": "dealer_surrenders", "to": room.players[target]["name"]})
                    await check_and_resolve(room)

            elif act == "set_dealer":
                code = players_room.get(pid, "")
                if code not in rooms: continue
                room = rooms[code]
                nd = msg.get("dealer_pid", "")
                if nd in room.players:
                    room.dealer_pid = nd
                    await room.send_state_to_all()

            elif act == "toggle_four_big":
                code = players_room.get(pid, "")
                if code not in rooms: continue
                room = rooms[code]
                room.four_big_enabled = not room.four_big_enabled
                await room.broadcast({"type": "four_big_toggled", "enabled": room.four_big_enabled})

            elif act == "add_ai":
                code = players_room.get(pid, "")
                if code not in rooms: continue
                room = rooms[code]
                ai_count = sum(1 for v in room.players.values() if v.get("is_ai"))
                if ai_count >= 5: continue
                ai_name = random.choice(["老张","阿强","大刘","肥仔","阿龙","小明","阿华","阿杰"])
                ai_pid = "ai_" + str(random.randint(10000, 99999))
                room.add_player(None, ai_name, ai_pid, is_ai=True)
                await room.broadcast({"type": "ai_joined", "name": ai_name, "pid": ai_pid})
                await room.send_state_to_all()

            elif act == "remove_ai":
                code = players_room.get(pid, "")
                if code not in rooms: continue
                room = rooms[code]
                target = msg.get("ai_pid", "")
                if target in room.players and room.players[target].get("is_ai"):
                    name = room.players[target]["name"]
                    room.remove_player(target)
                    await room.broadcast({"type": "ai_left", "name": name})
                    await room.send_state_to_all()

    except Exception as e:
        print(f"Error: {e}")
    finally:
        for code, r in list(rooms.items()):
            if pid in r.players:
                r.remove_player(pid)
                if not [p for p in r.players if not r.players[p].get("is_ai")]:
                    del rooms[code]
                else:
                    asyncio.ensure_future(r.send_state_to_all())
        if pid in players_room:
            del players_room[pid]

class GameHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            try:
                with open("index.html", "rb") as f:
                    self.wfile.write(f.read())
            except:
                self.wfile.write(b"HTML not found")
        else:
            self.send_response(404)
            self.end_headers()

def start_http(port):
    httpd = http.server.HTTPServer(("0.0.0.0", port), GameHTTPHandler)
    httpd.serve_forever()

async def main():
    import os
    ws_port = int(os.environ.get("PORT", 8000)) + 1
    http_port = int(os.environ.get("PORT", 8000))
    threading.Thread(target=start_http, args=(http_port,), daemon=True).start()
    async with serve(ws_handler, "0.0.0.0", ws_port):
        print(f"Server running: HTTP={http_port}, WS={ws_port}")
        await asyncio.get_running_loop().create_future()

asyncio.run(main())
