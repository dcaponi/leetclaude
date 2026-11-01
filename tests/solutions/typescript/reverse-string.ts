/**
 Do not return anything, modify s in-place instead.
 */
function reverseString(s: string[]): void {
    for (let l = 0, r = s.length - 1; l < r; l++, r--) {
        const tmp: string = s[l];
        s[l] = s[r];
        s[r] = tmp;
    }
};
