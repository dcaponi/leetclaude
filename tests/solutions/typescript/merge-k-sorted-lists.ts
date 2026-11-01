/**
 * Definition for singly-linked list.
 * class ListNode {
 *     val: number
 *     next: ListNode | null
 *     constructor(val?: number, next?: ListNode | null) {
 *         this.val = (val===undefined ? 0 : val)
 *         this.next = (next===undefined ? null : next)
 *     }
 * }
 */

function mergeKLists(lists: Array<ListNode | null>): ListNode | null {
    const values: number[] = [];
    for (let node of lists) {
        while (node) {
            values.push(node.val);
            node = node.next;
        }
    }
    values.sort((a, b) => a - b);
    const dummy = new ListNode(0);
    let tail: ListNode = dummy;
    for (const v of values) {
        tail.next = new ListNode(v);
        tail = tail.next;
    }
    return dummy.next;
};
