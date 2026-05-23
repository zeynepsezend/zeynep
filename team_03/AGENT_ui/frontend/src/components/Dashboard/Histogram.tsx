import React, { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

export interface HistogramProps {
  data: number[];
  label: string;
  color?: string;
}

interface BinEntry {
  range: string;
  count: number;
  binStart: number;
}

const autoBin = (data: number[], numBins = 10): BinEntry[] => {
  if (!data || data.length === 0) return [];
  const min = Math.min(...data);
  const max = Math.max(...data);
  if (min === max) {
    return [{ range: String(min.toFixed(2)), count: data.length, binStart: min }];
  }
  const binWidth = (max - min) / numBins;
  const bins: BinEntry[] = Array.from({ length: numBins }, (_, i) => {
    const start = min + i * binWidth;
    const end = start + binWidth;
    return {
      range: `${start.toFixed(1)}–${end.toFixed(1)}`,
      count: 0,
      binStart: start,
    };
  });

  for (const val of data) {
    let idx = Math.floor((val - min) / binWidth);
    if (idx >= numBins) idx = numBins - 1;
    bins[idx].count += 1;
  }

  return bins;
};

const CustomTooltip: React.FC<{
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}> = ({ active, payload, label }) => {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div style={{
      background: 'rgba(10, 14, 23, 0.95)',
      border: '1px solid rgba(0,229,255,0.2)',
      borderRadius: '6px',
      padding: '6px 10px',
      fontSize: '11px',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
      color: '#e0e6ed',
    }}>
      <div style={{ color: '#6b7b8d', marginBottom: '2px' }}>{label}</div>
      <div style={{ color: '#00E5FF', fontWeight: 600 }}>{payload[0].value} entries</div>
    </div>
  );
};

const Histogram: React.FC<HistogramProps> = ({ data, label, color = '#00E5FF' }) => {
  const bins = useMemo(() => autoBin(data ?? [], 10), [data]);

  const containerStyle: React.CSSProperties = {
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
  };

  const titleStyle: React.CSSProperties = {
    color: '#6b7b8d',
    fontSize: '11px',
    letterSpacing: '0.06em',
    textTransform: 'uppercase',
    marginBottom: '10px',
  };

  if (!data || data.length === 0) {
    return (
      <div style={containerStyle}>
        <div style={titleStyle}>{label}</div>
        <div style={{ color: '#6b7b8d', fontSize: '12px', textAlign: 'center', padding: '20px' }}>
          No data available
        </div>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      <div style={titleStyle}>{label}</div>
      <ResponsiveContainer width="100%" height={130}>
        <BarChart data={bins} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <XAxis
            dataKey="range"
            tick={{ fill: '#6b7b8d', fontSize: 9 }}
            tickLine={false}
            axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
            interval="preserveStartEnd"
          />
          <YAxis
            allowDecimals={false}
            tick={{ fill: '#6b7b8d', fontSize: 9 }}
            tickLine={false}
            axisLine={false}
            width={30}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(0,229,255,0.05)' }} />
          <Bar dataKey="count" radius={[3, 3, 0, 0]}>
            {bins.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={color}
                fillOpacity={0.6 + (entry.count / Math.max(...bins.map(b => b.count))) * 0.4}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default React.memo(Histogram);
