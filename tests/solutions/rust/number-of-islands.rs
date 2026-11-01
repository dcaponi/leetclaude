impl Solution {
    pub fn num_islands(grid: Vec<Vec<char>>) -> i32 {
        let mut grid = grid;
        let mut count = 0;
        for r in 0..grid.len() {
            for c in 0..grid[0].len() {
                if grid[r][c] == '1' {
                    count += 1;
                    Self::sink(&mut grid, r as i32, c as i32);
                }
            }
        }
        count
    }

    fn sink(grid: &mut Vec<Vec<char>>, r: i32, c: i32) {
        if r < 0 || c < 0 || r as usize >= grid.len() || c as usize >= grid[0].len() {
            return;
        }
        let (ru, cu) = (r as usize, c as usize);
        if grid[ru][cu] != '1' {
            return;
        }
        grid[ru][cu] = '0';
        Self::sink(grid, r + 1, c);
        Self::sink(grid, r - 1, c);
        Self::sink(grid, r, c + 1);
        Self::sink(grid, r, c - 1);
    }
}
