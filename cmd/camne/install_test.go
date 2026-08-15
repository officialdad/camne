package main

import "testing"

func TestProgressLine(t *testing.T) {
	const mb = 1_000_000
	for _, tc := range []struct {
		name       string
		got, total int64
		rate       float64
		want       string
	}{
		{"nothing measured yet omits speed and estimate", 0, 986 * mb, -1,
			"  [........................]   0%  0/986 MB"},
		{"halfway", 493 * mb, 986 * mb, 16 * mb,
			"  [############............]  50%  493/986 MB  16.0 MB/s  31s left"},
		// The reason the speed is on the line at all: stopped must not read
		// the same as slow.
		{"stalled shows zero speed and no estimate", 400 * mb, 986 * mb, 0,
			"  [#########...............]  40%  400/986 MB  0.0 MB/s"},
		{"minutes left", 100 * mb, 986 * mb, 3 * mb,
			"  [##......................]  10%  100/986 MB  3.0 MB/s  4m 55s left"},
		{"a crawl is phrased, not counted", 10 * mb, 986 * mb, 1000,
			"  [........................]   1%  10/986 MB  0.0 MB/s  over an hour left"},
		// The last frame drops the estimate: "0s left" under a full bar is noise.
		{"complete", 986 * mb, 986 * mb, 16 * mb,
			"  [########################] 100%  986/986 MB  16.0 MB/s"},
		// A resumed .part measured against a stale total must not print a bar
		// longer than the bar or a percentage over 100.
		{"overshoot is clamped", 999 * mb, 986 * mb, -1,
			"  [########################] 100%  986/986 MB"},
		{"unknown total falls back to a counter", 42 * mb, 0, -1, "  42 MB"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			if got := progressLine(tc.got, tc.total, tc.rate); got != tc.want {
				t.Errorf("progressLine(%d, %d, %v)\n got %q\nwant %q",
					tc.got, tc.total, tc.rate, got, tc.want)
			}
		})
	}
}

// A stall has to become visible on the line within a few seconds, and a burst
// must not be believed on the strength of one sample. Both are the same knob.
func TestSmoothRateDecaysOnAStall(t *testing.T) {
	const mb = 1_000_000
	if got := smoothRate(-1, 20*mb); got != 20*mb {
		t.Fatalf("first sample should be taken whole, got %v", got)
	}
	// Steady at 20 MB/s, then the connection dies: four ticks is two seconds.
	rate := 20.0 * mb
	for i := 0; i < 4; i++ {
		rate = smoothRate(rate, 0)
	}
	if rate > 5*mb {
		t.Errorf("after 2s of no bytes the rate still reads %.1f MB/s; a stall must be visible", rate/mb)
	}
	// One fast sample must not triple the displayed speed.
	if got := smoothRate(10*mb, 60*mb); got > 25*mb {
		t.Errorf("single burst moved the rate to %.1f MB/s, too twitchy", got/mb)
	}
}

func TestETA(t *testing.T) {
	for _, tc := range []struct {
		secs float64
		want string
	}{
		{0, "almost done"},
		{0.4, "almost done"},
		{1.4, "1s left"},
		{59, "59s left"},
		{59.6, "1m 0s left"}, // rounds up across the boundary, not down to 59s
		{60, "1m 0s left"},
		{125, "2m 5s left"},
		{3599, "59m 59s left"},
		{3600, "over an hour left"},
		{86400, "over an hour left"},
	} {
		if got := eta(tc.secs); got != tc.want {
			t.Errorf("eta(%v) = %q, want %q", tc.secs, got, tc.want)
		}
	}
}
