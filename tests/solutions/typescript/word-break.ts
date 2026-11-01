function wordBreak(s: string, wordDict: string[]): boolean {
    const dict = new Set<string>(wordDict);
    const memo = new Map<number, boolean>();
    const can = (start: number): boolean => {
        if (start === s.length) return true;
        if (memo.has(start)) return memo.get(start)!;
        let ok = false;
        for (let end = start + 1; end <= s.length && !ok; end++) {
            if (dict.has(s.substring(start, end)) && can(end)) ok = true;
        }
        memo.set(start, ok);
        return ok;
    };
    return can(0);
};
