"use client";
import React, { useEffect } from "react";
import { SigmaContainer, ControlsContainer, ZoomControl, FullScreenControl } from "@react-sigma/core";
import { useLoadGraph, useSigma } from "@react-sigma/core";
import { useWorkerLayoutForceAtlas2 } from "@react-sigma/layout-forceatlas2";
import Graph from "graphology";
import "@react-sigma/core/lib/style.css";
import { useAppContext } from "@/context/AppContext";

const HighlightingSystem = () => {
  const sigma = useSigma();
  const { highlightedNodes } = useAppContext();

  useEffect(() => {
    const graph = sigma.getGraph();
    if (!graph) return;

    if (highlightedNodes.length === 0) {
      // Reset everything to original colors
      graph.forEachNode((n, attrs) => {
        graph.setNodeAttribute(n, "hidden", false);
        graph.setNodeAttribute(n, "color", attrs.originalColor || attrs.color);
        graph.setNodeAttribute(n, "label", attrs.originalLabel || attrs.label);
      });
      graph.forEachEdge((e) => {
        graph.setEdgeAttribute(e, "hidden", false);
      });
      return;
    }

    // Highlight specific nodes
    graph.forEachNode((n, attrs) => {
      // Save original attrs if not saved
      if (!attrs.originalColor) graph.setNodeAttribute(n, "originalColor", attrs.color);
      if (!attrs.originalLabel) graph.setNodeAttribute(n, "originalLabel", attrs.label);

      if (highlightedNodes.includes(n)) {
        graph.setNodeAttribute(n, "hidden", false);
        graph.setNodeAttribute(n, "color", "#F59E0B"); // Bright Amber for highlighted
      } else {
        graph.setNodeAttribute(n, "color", "#E2E8F0"); // Faded gray for others
        graph.setNodeAttribute(n, "label", ""); // Hide labels for non-highlighted
      }
    });

    graph.forEachEdge((e, attrs, source, target) => {
      if (highlightedNodes.includes(source) || highlightedNodes.includes(target)) {
        graph.setEdgeAttribute(e, "hidden", false);
        graph.setEdgeAttribute(e, "color", "#94a3b8");
      } else {
        graph.setEdgeAttribute(e, "hidden", true);
      }
    });
  }, [sigma, highlightedNodes]);

  return null;
};

const LoadGraphAndLayout = ({ graphData }: { graphData: any }) => {
  const loadGraph = useLoadGraph();
  const { start, stop, kill } = useWorkerLayoutForceAtlas2({ settings: { slowDown: 10, linLogMode: true } });

  useEffect(() => {
    if (!graphData || !graphData.nodes) return;
    
    const graph = new Graph();
    graphData.nodes.forEach((n: any) => {
      // Color map based on PRD types
      const colorMap: Record<string, string> = {
        "CHARACTER": "#2563EB", // Blue
        "PLACE": "#10B981", // Green
        "EVENT": "#F97316", // Orange
        "OBJECT": "#8B5CF6", // Purple
        "THEME": "#6B7280"  // Gray
      };
      
      const nodeColor = colorMap[n.type] || "#2563EB";
      if (!graph.hasNode(n.id)) {
        graph.addNode(n.id, { 
          x: Math.random() * 100, 
          y: Math.random() * 100, 
          size: 15, 
          label: n.id, 
          color: nodeColor,
          originalColor: nodeColor,
          originalLabel: n.id,
          ...n 
        });
      }
    });

    graphData.edges.forEach((e: any) => {
      if (graph.hasNode(e.source) && graph.hasNode(e.target) && !graph.hasEdge(e.source, e.target)) {
        graph.addEdge(e.source, e.target, { 
          type: "line", 
          size: 2, 
          color: "#94a3b8",
          label: e.type,
          ...e 
        });
      }
    });

    loadGraph(graph);
    
    // Start layout
    start();
    
    // Stop after few seconds to stabilize
    const timer = setTimeout(() => {
      stop();
    }, 3500);

    return () => {
      clearTimeout(timer);
      kill();
    };
  }, [graphData, loadGraph, start, stop, kill]);

  return null;
};

export const GraphVisualization = ({ graphData }: { graphData: any }) => {
  return (
    <div className="w-full h-full bg-[var(--color-surface)] border-l border-[var(--color-border)] relative">
      {!graphData ? (
        <div className="flex items-center justify-center h-full text-gray-500">Loading graph...</div>
      ) : (
        <SigmaContainer style={{ width: "100%", height: "100%" }} settings={{ allowInvalidContainer: true, labelFont: "Inter, sans-serif" }}>
          <LoadGraphAndLayout graphData={graphData} />
          <HighlightingSystem />
          <ControlsContainer position={"bottom-right"}>
            <ZoomControl />
            <FullScreenControl />
          </ControlsContainer>
        </SigmaContainer>
      )}
    </div>
  );
};
