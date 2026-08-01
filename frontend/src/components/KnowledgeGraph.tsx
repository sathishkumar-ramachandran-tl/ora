import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
import { Company, Project } from '../types';
import { Sparkles, ArrowRight, Target, Award, MousePointerClick, X } from 'lucide-react';

interface KnowledgeGraphProps {
  companies: Company[];
  onNavigate: (type: 'project' | 'company', id: string) => void;
}

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  group: number;
  r: number;
  type?: string;
  data?: any;
  color?: string;
}

interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
  source: string | GraphNode;
  target: string | GraphNode;
}

export const KnowledgeGraph: React.FC<KnowledgeGraphProps> = ({ companies, onNavigate }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [selectedNode, setSelectedNode] = useState<{ type: 'project' | 'company' | 'root'; data: any } | null>(null);

  // ResizeObserver: always know the real container pixel size
  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) setDimensions({ width, height });
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!svgRef.current || companies.length === 0) return;
    const { width, height } = dimensions;
    if (width === 0 || height === 0) return;

    const LABEL_MARGIN = 28; // extra space below node for text label
    const EDGE_PAD = 50;     // keep nodes this many px from container edge

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    // Build nodes + links
    const nodes: GraphNode[] = [];
    const links: GraphLink[] = [];

    nodes.push({ id: 'ME', group: 0, r: 40, data: { name: 'Central Intelligence' } });

    companies.forEach((company, cIdx) => {
      nodes.push({
        id: company.name,
        group: cIdx + 1,
        r: 30,
        color: company.color,
        type: 'company',
        data: company,
      });
      links.push({ source: 'ME', target: company.name });

      company.projects.forEach(proj => {
        const progressRadius = 15 + (proj.progress / 100) * 20;
        nodes.push({
          id: proj.name,
          group: cIdx + 1,
          r: progressRadius,
          type: 'project',
          data: { ...proj, companyName: company.name, companyColor: company.color },
        });
        links.push({ source: company.name, target: proj.name });
      });
    });

    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id((d: any) => d.id)
        .distance((d: any) => (d.target as GraphNode).type === 'project' ? 90 : 160))
      .force('charge', d3.forceManyBody().strength(-500))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collide', d3.forceCollide().radius((d: any) => d.r + 14))
      // Boundary: keep nodes inside visible area including room for labels
      .force('bound-x', () => {
        nodes.forEach(d => {
          const lo = EDGE_PAD + d.r;
          const hi = width - EDGE_PAD - d.r;
          if (d.x! < lo) d.x = lo;
          if (d.x! > hi) d.x = hi;
        });
      })
      .force('bound-y', () => {
        nodes.forEach(d => {
          const lo = EDGE_PAD + d.r;
          // Extra bottom margin for text label
          const hi = height - EDGE_PAD - d.r - LABEL_MARGIN;
          if (d.y! < lo) d.y = lo;
          if (d.y! > hi) d.y = hi;
        });
      });

    // Links
    const link = svg.append('g')
      .attr('stroke', '#e2e8f0')
      .attr('stroke-opacity', 0.7)
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke-width', 2);

    // Node groups
    const nodeGroup = svg.append('g')
      .selectAll('g')
      .data(nodes)
      .join('g')
      .call((d3.drag() as any)
        .on('start', (event: any, d: any) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x; d.fy = d.y;
        })
        .on('drag', (event: any, d: any) => {
          d.fx = Math.max(EDGE_PAD + d.r, Math.min(width - EDGE_PAD - d.r, event.x));
          d.fy = Math.max(EDGE_PAD + d.r, Math.min(height - EDGE_PAD - d.r - LABEL_MARGIN, event.y));
        })
        .on('end', (event: any, d: any) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null; d.fy = null;
        }))
      .on('click', (event: any, d: any) => {
        event.stopPropagation();
        setSelectedNode(d.id === 'ME' ? null : { type: d.type as any, data: d.data });
      });

    // Glow ring for completed projects
    nodeGroup.filter((d: any) => d.type === 'project' && d.data.progress === 100)
      .append('circle')
      .attr('r', (d: any) => d.r + 6)
      .attr('fill', 'none')
      .attr('stroke', '#eab308')
      .attr('stroke-width', 2)
      .attr('stroke-opacity', 0.6)
      .attr('stroke-dasharray', '4 2');

    // Main circles
    nodeGroup.append('circle')
      .attr('r', (d: any) => d.r)
      .attr('fill', (d: any) => {
        if (d.id === 'ME') return '#1e293b';
        if (d.type === 'company') return `var(--color-${d.color}-500, #6366f1)`;
        if (d.data?.type === 'learning') return '#10b981';
        if (d.data?.type === 'build') return '#3b82f6';
        if (d.data?.type === 'client') return '#8b5cf6';
        return '#64748b';
      })
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .attr('class', 'cursor-pointer hover:opacity-90 transition-opacity duration-200');

    // Text labels — rendered OUTSIDE the node (below), won't clip because SVG has overflow:visible
    nodeGroup.append('text')
      .text((d: any) => d.id)
      .attr('text-anchor', 'middle')
      .attr('dy', (d: any) => d.r + 16)
      .attr('fill', '#475569')
      .attr('font-size', '10px')
      .attr('font-weight', '600')
      .style('pointer-events', 'none')
      .style('text-shadow', '0 1px 3px rgba(255,255,255,0.9), 0 1px 3px rgba(255,255,255,0.9)');

    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);
      nodeGroup.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });

    return () => { simulation.stop(); };
  }, [companies, dimensions]);

  return (
    <div
      ref={containerRef}
      className="w-full h-full bg-slate-50 relative rounded-xl border border-slate-200 group"
      style={{ overflow: 'hidden' }}
      onClick={() => setSelectedNode(null)}
    >
      {/* Legend */}
      <div className="absolute top-4 left-4 z-10 bg-white/90 backdrop-blur p-3 rounded-lg shadow-sm border border-slate-200 text-xs">
        <h4 className="font-bold text-slate-700 mb-2">Neural Legend</h4>
        <div className="flex items-center gap-2 mb-1"><div className="w-3 h-3 rounded-full bg-blue-500" />Build</div>
        <div className="flex items-center gap-2 mb-1"><div className="w-3 h-3 rounded-full bg-emerald-500" />Learning</div>
        <div className="flex items-center gap-2 mb-2"><div className="w-3 h-3 rounded-full bg-violet-500" />Client</div>
        <div className="h-px bg-slate-200 my-2" />
        <div className="flex items-center gap-2 text-slate-500">
          <div className="w-2 h-2 rounded-full bg-slate-400" />
          <ArrowRight size={10} />
          <div className="w-4 h-4 rounded-full bg-slate-400" />
          <span>Size = Progress</span>
        </div>
      </div>

      <div className="absolute bottom-4 left-4 z-10 text-slate-400 text-xs flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
        <MousePointerClick size={14} /> Click nodes to inspect · Drag to reposition
      </div>

      {/* SVG: overflow=visible so text labels below nodes are never clipped */}
      <svg
        ref={svgRef}
        width={dimensions.width}
        height={dimensions.height}
        style={{ display: 'block', overflow: 'visible' }}
      />

      {/* Synapse Inspector */}
      {selectedNode && (
        <div
          className="absolute top-4 bottom-4 right-4 w-72 bg-white/95 backdrop-blur shadow-2xl rounded-xl border border-slate-200 flex flex-col overflow-hidden animate-in slide-in-from-right-10 duration-300"
          onClick={e => e.stopPropagation()}
        >
          <div className="p-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-start">
            <div>
              <h3 className="font-bold text-slate-800 text-base leading-tight">{selectedNode.data.name}</h3>
              {selectedNode.type === 'project' && (
                <span className={`inline-block mt-1 text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700`}>
                  {selectedNode.data.type}
                </span>
              )}
            </div>
            <button onClick={() => setSelectedNode(null)} className="text-slate-400 hover:text-slate-600 flex-shrink-0">
              <X size={16} />
            </button>
          </div>

          <div className="p-4 flex-1 overflow-y-auto">
            {selectedNode.type === 'project' ? (
              <div className="space-y-5">
                <div>
                  <h4 className="text-xs font-bold text-slate-500 uppercase flex items-center gap-2 mb-2">
                    <Target size={11} /> Target Outcome
                  </h4>
                  <p className="text-sm text-slate-700 leading-relaxed">
                    {selectedNode.data.mission || 'No mission statement defined.'}
                  </p>
                </div>
                <div>
                  <div className="flex justify-between items-end mb-2">
                    <h4 className="text-xs font-bold text-slate-500 uppercase flex items-center gap-2">
                      <Award size={11} /> Completion
                    </h4>
                    <span className="text-lg font-mono font-bold text-indigo-600">{selectedNode.data.progress}%</span>
                  </div>
                  <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-indigo-500 transition-all duration-700" style={{ width: `${selectedNode.data.progress}%` }} />
                  </div>
                </div>
                <div className="bg-slate-50 rounded-lg p-3 border border-slate-200 space-y-1.5">
                  <div className="flex justify-between text-xs text-slate-600">
                    <span>Active Tasks</span>
                    <span className="font-mono font-semibold">
                      {selectedNode.data.tasks.filter((t: any) => t.status !== 'done').length}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs text-slate-600">
                    <span>Hours Remaining</span>
                    <span className="font-mono font-semibold">
                      {selectedNode.data.tasks
                        .filter((t: any) => t.status !== 'done')
                        .reduce((acc: number, t: any) => acc + (t.estimatedHours || 0), 0)}h
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-xs text-slate-500 uppercase font-semibold">Initiative Container</p>
                <p className="text-sm text-slate-700 leading-relaxed">{selectedNode.data.mission}</p>
                <div className="bg-slate-50 p-3 rounded-lg border border-slate-100 text-center">
                  <div className="text-xl font-bold text-slate-800">{selectedNode.data.projects.length}</div>
                  <div className="text-[10px] text-slate-500 uppercase">Projects</div>
                </div>
              </div>
            )}
          </div>

          {selectedNode.type === 'project' && (
            <div className="p-4 border-t border-slate-100 bg-slate-50">
              <button
                onClick={() => onNavigate('project', selectedNode.data.id)}
                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 rounded-lg flex items-center justify-center gap-2 transition-colors shadow-sm shadow-indigo-200 text-sm"
              >
                <Sparkles size={14} /> Jump to Neural Board
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
