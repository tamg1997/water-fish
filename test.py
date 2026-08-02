import sys
sys.path.insert(0, 'D:/AIProgramming/water_fish')
with open('D:/AIProgramming/water_fish/server.py', encoding='utf-8') as f:
    code = f.read()
code = code.split('async def main')[0]
exec(code)

deck = make_deck()
print(f'牌数: {len(deck)}')

# 至尊水鱼
cards = [{'rank':'A','suit':'S'},{'rank':'A','suit':'H'},{'rank':'A','suit':'C'},{'rank':'A','suit':'D'}]
ht = get_hand_type(cards)
print(f'AAAA: {get_hand_display(ht)}, 乌龙={ht["is_wulong"]}, 至尊={ht["is_supreme"]}')

# 水鱼
cards2 = [{'rank':'K','suit':'S'},{'rank':'K','suit':'H'},{'rank':'5','suit':'C'},{'rank':'5','suit':'D'}]
ht2 = get_hand_type(cards2)
print(f'KK55: {get_hand_display(ht2)}, 乌龙={ht2["is_wulong"]}')

# 双麻麻
cards3 = [{'rank':'K','suit':'S'},{'rank':'Q','suit':'H'},{'rank':'10','suit':'C'},{'rank':'10','suit':'D'}]
ht3 = get_hand_type(cards3)
print(f'KQ+1010: {get_hand_display(ht3)}, 双零={ht3["is_double_zero"]}')

# 乌龙测试
cards4 = [{'rank':'A','suit':'S'},{'rank':'A','suit':'H'},{'rank':'K','suit':'C'},{'rank':'2','suit':'D'}]
ht4 = get_hand_type(cards4)
print(f'AA+K2(应头AA尾K2): 乌龙={ht4["is_wulong"]}, 头点={ht4["g1"]["point"]}, 尾点={ht4["g2"]["point"]}')

# AI
best = ai_best_grouping([{'rank':'8','suit':'S'},{'rank':'2','suit':'H'},{'rank':'7','suit':'C'},{'rank':'3','suit':'D'}])
print(f'AI分组: {best[0]}')
act = ai_choose_action(ht2)
print(f'AI水鱼操作: {act}')

# 比牌
r = compare_groups(
    {'point':8,'is_pair':False,'pair_rank':0,'max_rank':10,'max_suit':4},
    {'point':8,'is_pair':False,'pair_rank':0,'max_rank':10,'max_suit':3}
)
print(f'同点黑桃vs红桃: {r} (1=左赢)')

print('ALL OK')
