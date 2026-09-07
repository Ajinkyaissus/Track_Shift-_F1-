import { useMemo } from 'react';
import { useCircuit } from '../context/CircuitContext';

export default function ReplayControlBar() {
  const {
    replayLap,
    totalLaps,
    isPlaying,
    playbackSpeed,
    setReplayLap,
    togglePlay,
    setPlaybackSpeed,
    stepReplay,
    resetReplay
  } = useCircuit();

  // Generate milestone lap numbers for the visual timeline
  const timelineMilestones = useMemo(() => {
    const laps = [];
    laps.push(1);
    const step = Math.max(2, Math.round(totalLaps / 5));
    for (let i = step; i < totalLaps; i += step) {
      if (i !== 1 && i !== totalLaps) {
        laps.push(i);
      }
    }
    if (!laps.includes(totalLaps)) {
      laps.push(totalLaps);
    }
    return laps;
  }, [totalLaps]);

  return (
    <div className="replay-controls-panel">
      {/* Visual Lap Timeline */}
      <div className="timeline-container">
        <div className="timeline-header">
          <span className="timeline-title">RACE LAP TIMELINE</span>
          <div className="timeline-current-tag">
            LAP <span className="highlight-lap">{replayLap}</span> OF {totalLaps}
          </div>
        </div>

        <div className="timeline-track-wrapper">
          {/* Timeline Slider Input */}
          <input
            type="range"
            min="1"
            max={totalLaps}
            value={replayLap}
            onChange={(e) => setReplayLap(Number(e.target.value))}
            className="timeline-slider"
          />

          {/* Timeline Ticks & Milestones */}
          <div className="timeline-ticks">
            {timelineMilestones.map((lap) => {
              const isCurrent = lap === replayLap;
              const leftPct = ((lap - 1) / Math.max(1, totalLaps - 1)) * 100;
              return (
                <div 
                  key={lap} 
                  className={`timeline-milestone ${isCurrent ? 'active' : ''}`}
                  style={{ left: `${leftPct}%` }}
                  onClick={() => setReplayLap(lap)}
                >
                  <span className="milestone-tick"></span>
                  <span className="milestone-label">{lap}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Control Buttons & Replay Speed Toolbar */}
      <div className="controls-toolbar">
        {/* Playback Controls */}
        <div className="playback-btn-group">
          <button 
            className="ctrl-btn restart-btn"
            onClick={resetReplay}
            title="Restart Replay [R]"
          >
            ↺ Restart
          </button>

          <button 
            className="ctrl-btn step-btn"
            onClick={() => stepReplay(-1)}
            disabled={replayLap <= 1}
            title="Previous Lap [←]"
          >
            ◀ Prev Lap
          </button>

          <button 
            className={`ctrl-btn play-btn ${isPlaying ? 'playing' : ''}`}
            onClick={togglePlay}
            title="Play/Pause [SPACE]"
          >
            {isPlaying ? '❚❚ Pause' : '▶ Play Replay'}
          </button>

          <button 
            className="ctrl-btn step-btn"
            onClick={() => stepReplay(1)}
            disabled={replayLap >= totalLaps}
            title="Next Lap [→]"
          >
            Next Lap ▶
          </button>
        </div>

        {/* Speed Selector Buttons */}
        <div className="speed-btn-group">
          <span className="speed-label">SPEED:</span>
          {[1, 2, 4, 8].map((spd) => (
            <button
              key={spd}
              className={`speed-pill ${playbackSpeed === spd ? 'active' : ''}`}
              onClick={() => setPlaybackSpeed(spd)}
              title={`Replay Speed ${spd}x [${spd === 8 ? 4 : spd === 4 ? 3 : spd === 2 ? 2 : 1}]`}
            >
              {spd}x
            </button>
          ))}
        </div>

        {/* Keyboard Shortcut Hints */}
        <div className="keyboard-hints">
          <span className="key-hint"><strong>SPACE</strong> Play/Pause</span>
          <span className="key-hint"><strong>← / →</strong> Step Lap</span>
          <span className="key-hint"><strong>R</strong> Restart</span>
          <span className="key-hint"><strong>1-4</strong> Speed</span>
        </div>
      </div>
    </div>
  );
}
