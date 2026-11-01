/**
 * Definition for singly-linked list.
 * function ListNode(val, next) {
 *     this.val = (val===undefined ? 0 : val)
 *     this.next = (next===undefined ? null : next)
 * }
 */
/**
 * @param {ListNode[]} lists
 * @return {ListNode}
 */
var mergeKLists = function(lists) {
    const mergeTwo = (a, b) => {
        const dummy = new ListNode();
        let tail = dummy;
        while (a && b) {
            if (a.val <= b.val) { tail.next = a; a = a.next; }
            else { tail.next = b; b = b.next; }
            tail = tail.next;
        }
        tail.next = a || b;
        return dummy.next;
    };
    if (lists.length === 0) return null;
    while (lists.length > 1) {
        const next = [];
        for (let i = 0; i < lists.length; i += 2)
            next.push(i + 1 < lists.length ? mergeTwo(lists[i], lists[i + 1]) : lists[i]);
        lists = next;
    }
    return lists[0];
};
