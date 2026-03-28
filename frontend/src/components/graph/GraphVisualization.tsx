"use client";
import React, { useEffect, useState, useMemo } from "react";
import { SigmaContainer, ControlsContainer, ZoomControl, FullScreenControl } from "@react-sigma/core";
import { useLoadGraph, useSigma, useRegisterEvents, useSetSettings } from "@react-sigma/core";
import { useWorkerLayoutForceAtlas2 } from "@react-sigma/layout-forceatlas2";
import { MultiDirectedGraph } from "graphology";
import "@react-sigma/core/lib/style.css";
import { useAppContext } from "@/context/AppContext";

/**
 * HoverSystem: Manages node/edge highlighting on hover
 */
const HoverSystem = () => {
  const sigma = useSigma();
  const registerEvents = useRegisterEvents();
  const setSettings = useSetSettings();
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  useEffect(() => {
    registerEvents({
      enterNode: (event) => setHoveredNode(event.node),
      leaveNode: () => setHoveredNode(null),
    });
  }, [registerEvents]);

  useEffect(() => {
    setSettings({
      nodeReducer: (node, data) => {
        const graph = sigma.getGraph();
        if (hoveredNode) {
          if (node === hoveredNode || graph.hasEdge(node, hoveredNode) || graph.hasEdge(hoveredNode, node)) {
            return { ...data, zIndex: 1 };
          } else {
            return { ...data, color: "rgba(148, 163, 184, 0.1)", label: "", zIndex: 0 };
          }
        }
        return data;
      },
      edgeReducer: (edge, data) => {
        const graph = sigma.getGraph();
        if (hoveredNode) {
          if (graph.source(edge) === hoveredNode || graph.target(edge) === hoveredNode) {
            return { ...data, color: "var(--color-primary)", size: 4, zIndex: 1 };
          } else {
            return { ...data, color: "rgba(148, 163, 184, 0.05)", zIndex: 0 };
          }
        }
        return data;
      },
    });
  }, [hoveredNode, setSettings, sigma]);

  return null;
};

const HighlightingSystem = () => {
  const sigma = useSigma();
  const { highlightedNodes } = useAppContext();

  useEffect(() => {
    const graph = sigma.getGraph();
    if (!graph) return;

    if (highlightedNodes.length === 0) {
      graph.forEachNode((n, attrs) => {
        graph.setNodeAttribute(n, "hidden", false);
        graph.setNodeAttribute(n, "color", attrs.originalColor || attrs.color);
        graph.setNodeAttribute(n, "label", attrs.originalLabel || attrs.label);
      });
      return;
    }

    graph.forEachNode((n, attrs) => {
      if (!attrs.originalColor) graph.setNodeAttribute(n, "originalColor", attrs.color);
      if (!attrs.originalLabel) graph.setNodeAttribute(n, "originalLabel", attrs.label);

      if (highlightedNodes.includes(n)) {
        graph.setNodeAttribute(n, "hidden", false);
        graph.setNodeAttribute(n, "color", "var(--color-accent)");
      } else {
        graph.setNodeAttribute(n, "color", "rgba(148, 163, 184, 0.2)");
        graph.setNodeAttribute(n, "label", ""); 
      }
    });
  }, [sigma, highlightedNodes]);

  return null;
};

const LoadGraphAndLayout = ({ graphData }: { graphData: any }) => {
  const loadGraph = useLoadGraph();
  const setSettings = useSetSettings();
  const { start, stop, kill } = useWorkerLayoutForceAtlas2({ 
    settings: { 
      gravity: 0.8,
      scalingRatio: 15,
      slowDown: 5,
      linLogMode: true,
      adjustSizes: true
    } 
  });

  // Update label color reactively when theme changes WITHOUT reloading the graph


  useEffect(() => {
    if (!graphData || !graphData.nodes) return;
    
    const graph = new MultiDirectedGraph();
    
    const colorMap: Record<string, string> = {
      "CHARACTER": "#60A5FA", // Brighter Blue
      "PLACE": "#34D399",    // Brighter Green
      "EVENT": "#FCD34D",    // Bright Amber
      "OBJECT": "#A78BFA",   // Brighter Purple
      "THEME": "#94A3B8"     // Muted Slate
    };

    const edgeColor = "rgba(15, 23, 42, 0.18)";

    graphData.nodes.forEach((n: any) => {
      const typeKey = (n.type || "").toUpperCase();
      const nodeColor = colorMap[typeKey] || "#60A5FA";
      
      if (!graph.hasNode(n.id)) {
        graph.addNode(n.id, { 
          x: Math.random() * 200, 
          y: Math.random() * 200, 
          size: 18, 
          label: n.id, 
          color: nodeColor,
          originalColor: nodeColor,
          originalLabel: n.id,
          ...n,
          type: "circle" 
        });
      }
    });

    graphData.edges.forEach((e: any) => {
      if (graph.hasNode(e.source) && graph.hasNode(e.target)) {
        const edgeId = `${e.source}-${e.target}-${e.relationship_type}`;
        if (!graph.hasEdge(edgeId)) {
          graph.addEdgeWithKey(edgeId, e.source, e.target, { 
            size: 2.5, 
            color: edgeColor,
            label: e.relationship_type,
            ...e,
            type: "arrow",
          });
        }
      }
    });

    loadGraph(graph);

    try {
      start();
    } catch (e) {
      // Worker may have been killed during a theme-switch remount; safe to ignore
    }
    
    const timer = setTimeout(() => stop(), 4000);
    return () => {
      clearTimeout(timer);
      stop();
    };
  // Intentionally exclude `theme` — theme changes go through setSettings, not graph reload
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graphData, loadGraph, start, stop]);

  // Kill the worker ONLY on true unmount
  useEffect(() => {
    return () => {
      try {
        kill();
      } catch (e) {
        // Safe to ignore
      }
    };
  }, [kill]);

  return null;
};

export const GraphVisualization = ({ graphData }: { graphData: any }) => {
  const customGraph = useMemo(() => new MultiDirectedGraph(), []);

  return (
    <div className="w-full h-full bg-transparent relative overflow-hidden">
      {!graphData ? (
        <div className="flex items-center justify-center h-full text-[var(--color-muted)] font-medium animate-pulse tracking-[0.2em] text-xs uppercase">
          Synthesizing Neural Map...
        </div>
      ) : (
        <SigmaContainer 
          graph={customGraph}
          className="sigma-container-root"
          style={{ width: "100%", height: "100%", background: "transparent" }} 
          settings={{ 
            allowInvalidContainer: true, 
            labelFont: "Outfit, Inter, sans-serif",
            // Initial value — LoadGraphAndLayout updates this via setSettings on theme change
            labelColor: { color: "#0F172A" },
            labelWeight: "700",
            labelSize: 13,
            edgeLabelFont: "Inter, sans-serif",
            edgeLabelSize: 10,
            edgeLabelColor: { color: "var(--color-muted)" },
            renderEdgeLabels: true,
            defaultEdgeType: "arrow",
            labelRenderedSizeThreshold: 12,
          }}
        >
          <LoadGraphAndLayout graphData={graphData} />
          <HighlightingSystem />
          <HoverSystem />
          <ControlsContainer position={"bottom-right"} className="!mr-6 !mb-6 !gap-3">
            <ZoomControl className="!bg-[var(--bg-secondary)] !text-[var(--text-primary)] !border-[var(--color-border)] hover:!bg-[var(--surface-hover)] !rounded-xl shadow-2xl transition-premium" />
            <FullScreenControl className="!bg-[var(--bg-secondary)] !text-[var(--text-primary)] !border-[var(--color-border)] hover:!bg-[var(--surface-hover)] !rounded-xl shadow-2xl transition-premium" />
          </ControlsContainer>
        </SigmaContainer>
      )}
    </div>
  );
};
