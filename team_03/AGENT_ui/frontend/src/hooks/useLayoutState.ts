import { useState, useCallback } from 'react';
import type { LayoutJSON } from '../types';
import type { NodeLinkData } from '../components/GraphPanel/graphDataMapper';
import type { ScoreData } from '../components/Dashboard/Dashboard';
import type { LayoutInfo } from '../components/LayoutLoader/LayoutLoader';
import type { StateUpdate } from '../utils/wsProtocol';

const API_BASE = '/api';

export interface UseLayoutStateReturn {
  layout: LayoutJSON | null;
  graphData: NodeLinkData | null;
  scores: ScoreData | null;
  availableLayouts: LayoutInfo[];
  selectedLayoutName: string | null;
  loadLayout: (name: string) => Promise<void>;
  uploadLayout: (file: File) => Promise<void>;
  fetchLayouts: () => Promise<void>;
  updateFromWS: (message: StateUpdate) => void;
}

export function useLayoutState(): UseLayoutStateReturn {
  const [layout, setLayout] = useState<LayoutJSON | null>(null);
  const [graphData, setGraphData] = useState<NodeLinkData | null>(null);
  const [scores, setScores] = useState<ScoreData | null>(null);
  const [availableLayouts, setAvailableLayouts] = useState<LayoutInfo[]>([]);
  const [selectedLayoutName, setSelectedLayoutName] = useState<string | null>(null);

  const fetchLayouts = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/layouts`);
      if (res.ok) {
        const data = await res.json();
        setAvailableLayouts(data);
      }
    } catch {
      // API not available, that's ok
    }
  }, []);

  const loadLayout = useCallback(async (name: string) => {
    try {
      setSelectedLayoutName(name);

      // Fetch layout data
      const layoutRes = await fetch(`${API_BASE}/layouts/${encodeURIComponent(name)}`);
      if (layoutRes.ok) {
        const layoutData = await layoutRes.json();
        setLayout(layoutData);
      }

      // Create/update session and fetch graph data
      try {
        await fetch(`${API_BASE}/session`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ layout_name: name }),
        });
      } catch {
        // Session endpoint may not be available
      }

      try {
        const graphRes = await fetch(`${API_BASE}/graph`);
        if (graphRes.ok) {
          const gData = await graphRes.json();
          setGraphData(gData);
        }
      } catch {
        // Graph endpoint may not be available
      }

      try {
        const scoresRes = await fetch(`${API_BASE}/scores`);
        if (scoresRes.ok) {
          const sData = await scoresRes.json();
          setScores(sData);
        }
      } catch {
        // Scores endpoint may not be available
      }
    } catch {
      // Layout fetch failed
    }
  }, []);

  const uploadLayout = useCallback(async (file: File) => {
    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(`${API_BASE}/layouts/upload`, {
        method: 'POST',
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        // Refresh layout list
        await fetchLayouts();
        // If upload returns layout data, load it
        if (data.layout) {
          setLayout(data.layout);
          setSelectedLayoutName(data.name ?? file.name.replace('.json', ''));
        } else if (data.name) {
          // Load the uploaded layout by name
          await loadLayout(data.name);
        }
      }
    } catch {
      // Upload failed, try loading file directly as layout
      try {
        const text = await file.text();
        const parsed = JSON.parse(text) as LayoutJSON;
        setLayout(parsed);
        setSelectedLayoutName(file.name.replace('.json', ''));
      } catch {
        // Could not parse file
      }
    }
  }, [fetchLayouts, loadLayout]);

  const updateFromWS = useCallback((message: StateUpdate) => {
    switch (message.field) {
      case 'layout':
        setLayout(message.data as LayoutJSON);
        break;
      case 'graph':
        setGraphData(message.data as NodeLinkData);
        break;
      case 'scores':
        setScores(message.data as ScoreData);
        break;
    }
  }, []);

  return {
    layout,
    graphData,
    scores,
    availableLayouts,
    selectedLayoutName,
    loadLayout,
    uploadLayout,
    fetchLayouts,
    updateFromWS,
  };
}
