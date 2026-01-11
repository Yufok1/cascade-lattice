"""
HuggingFace Hub Integration

Push and pull dataset provenance to/from HuggingFace Hub.

Exports complete W3C PROV-O accountability bundle:
- cascade_provenance.json (CASCADE native format)
- prov_o.jsonld (W3C PROV-O JSON-LD - interoperable)
- prov_n.txt (W3C PROV-N notation - human readable)
- activities.jsonl (Activity log for audit)
- agents.json (Agent attributions)
- croissant.json (MLCommons Croissant)
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .provenance import ProvenanceGraph
from .croissant import CroissantExporter


class AccountabilityBundle:
    """
    Complete W3C PROV-O accountability package.
    
    When a dataset is extracted, this bundle provides full audit trail:
    - Who created/modified it (agents)
    - What transformations occurred (activities)
    - Where it came from (entity lineage)
    - When everything happened (timestamps)
    - How to verify integrity (hashes)
    """
    
    def __init__(self, graph: ProvenanceGraph):
        self.graph = graph
        self.created_at = datetime.now(timezone.utc).isoformat()
    
    def to_prov_o_jsonld(self) -> Dict[str, Any]:
        """Export W3C PROV-O JSON-LD (interoperable standard)."""
        return self.graph.to_prov_jsonld()
    
    def to_prov_n(self) -> str:
        """Export W3C PROV-N notation (human readable)."""
        return self.graph.to_prov_n()
    
    def to_activity_log(self) -> List[Dict[str, Any]]:
        """Export activity log for audit (JSONL format)."""
        activities = []
        for activity in self.graph.list_activities():
            activities.append({
                "id": activity.id,
                "name": activity.name,
                "type": activity.activity_type.value,
                "started_at": datetime.fromtimestamp(activity.started_at).isoformat() if activity.started_at else None,
                "ended_at": datetime.fromtimestamp(activity.ended_at).isoformat() if activity.ended_at else None,
                "duration_seconds": activity.duration,
                "inputs": activity.inputs,
                "outputs": activity.outputs,
                "parameters": activity.parameters,
                "attributes": activity.attributes,
            })
        return activities
    
    def to_agent_attributions(self) -> Dict[str, Any]:
        """Export agent attributions for accountability."""
        agents = {}
        for agent in self.graph.list_agents():
            agents[agent.id] = {
                "name": agent.name,
                "type": agent.agent_type.value,
                "version": agent.version,
                "identifier": agent.identifier,
                "attributes": agent.attributes,
            }
        
        # Build attribution matrix: which agent did what
        attributions = []
        for rel in self.graph.list_relationships():
            if rel.relation_type.value == "wasAssociatedWith":
                activity = self.graph.get_activity(rel.source_id)
                agent = self.graph.get_agent(rel.target_id)
                if activity and agent:
                    attributions.append({
                        "activity_id": activity.id,
                        "activity_name": activity.name,
                        "agent_id": agent.id,
                        "agent_name": agent.name,
                        "timestamp": datetime.fromtimestamp(activity.started_at).isoformat() if activity.started_at else None,
                    })
        
        return {
            "agents": agents,
            "attributions": attributions,
            "total_agents": len(agents),
            "total_attributions": len(attributions),
        }
    
    def to_integrity_manifest(self) -> Dict[str, Any]:
        """Export integrity manifest for verification."""
        is_valid, invalid_ids = self.graph.verify_integrity()
        
        return {
            "root_hash": self.graph.root_hash,
            "created_at": self.created_at,
            "is_valid": is_valid,
            "invalid_entity_ids": invalid_ids,
            "entity_hashes": {
                entity.id: {
                    "content_hash": entity.content_hash,
                    "schema_hash": entity.schema_hash,
                }
                for entity in self.graph.list_entities()
            },
            "verification_note": (
                "To verify: recompute content hashes and compare against this manifest. "
                "Any mismatch indicates data tampering."
            ),
        }
    
    def export(self, output_dir: str):
        """Export all accountability artifacts to a directory."""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        # 1. CASCADE provenance JSON
        with open(os.path.join(output_dir, "cascade_provenance.json"), "w") as f:
            json.dump(self.graph.to_dict(), f, indent=2, default=str)
        
        # 2. W3C PROV-O JSON-LD
        with open(os.path.join(output_dir, "prov_o.jsonld"), "w") as f:
            json.dump(self.to_prov_o_jsonld(), f, indent=2, default=str)
        
        # 3. W3C PROV-N notation
        with open(os.path.join(output_dir, "prov_n.txt"), "w") as f:
            f.write(self.to_prov_n())
        
        # 4. Activity log
        with open(os.path.join(output_dir, "activities.jsonl"), "w") as f:
            for activity in self.to_activity_log():
                f.write(json.dumps(activity, default=str) + "\n")
        
        # 5. Agent attributions
        with open(os.path.join(output_dir, "agents.json"), "w") as f:
            json.dump(self.to_agent_attributions(), f, indent=2, default=str)
        
        # 6. Integrity manifest
        with open(os.path.join(output_dir, "integrity_manifest.json"), "w") as f:
            json.dump(self.to_integrity_manifest(), f, indent=2, default=str)
            
        # 7. Croissant metadata
        exporter = CroissantExporter(self.graph)
        croissant_content = exporter.to_json(name="dataset", url="local://")
        with open(os.path.join(output_dir, "croissant.json"), "w") as f:
            f.write(croissant_content)
    
    def summary(self) -> Dict[str, Any]:
        """Summary of the accountability bundle."""
        stats = self.graph.stats
        return {
            "bundle_created_at": self.created_at,
            "graph_name": self.graph.name,
            "root_hash": self.graph.root_hash,
            "entities": stats["entities"],
            "activities": stats["activities"],
            "agents": stats["agents"],
            "relationships": stats["relationships"],
            "files_included": [
                "cascade_provenance.json",
                "prov_o.jsonld",
                "prov_n.txt",
                "activities.jsonl",
                "agents.json",
                "integrity_manifest.json",
                "croissant.json",
            ],
        }


class HubIntegration:
    """
    Integration with HuggingFace Hub for dataset provenance.
    
    Stores complete accountability bundle:
    1. cascade_provenance.json - CASCADE native format
    2. prov_o.jsonld - W3C PROV-O JSON-LD (interoperable)
    3. prov_n.txt - W3C PROV-N notation (human readable)
    4. activities.jsonl - Activity log for audit
    5. agents.json - Agent attributions
    6. integrity_manifest.json - Hash verification
    7. croissant.json - MLCommons Croissant
    8. README.md - Human-readable provenance section
    """
    
    PROVENANCE_FILENAME = "cascade_provenance.json"
    PROV_O_FILENAME = "prov_o.jsonld"
    PROV_N_FILENAME = "prov_n.txt"
    ACTIVITIES_FILENAME = "activities.jsonl"
    AGENTS_FILENAME = "agents.json"
    INTEGRITY_FILENAME = "integrity_manifest.json"
    CROISSANT_FILENAME = "croissant.json"
    
    def __init__(self, token: str = None):
        """
        Initialize Hub integration.
        
        Args:
            token: HuggingFace API token (optional, uses cached token if not provided)
        """
        self.token = token
    
    def push_provenance(
        self,
        graph: ProvenanceGraph,
        repo_id: str,
        commit_message: str = "Update provenance",
        private: bool = False,
        include_croissant: bool = True,
        full_accountability: bool = True,
    ) -> str:
        """
        Push complete accountability bundle to HuggingFace Hub.
        
        Args:
            graph: The provenance graph to push
            repo_id: HuggingFace repo ID (e.g., "username/dataset-name")
            commit_message: Commit message
            private: Whether the repo should be private
            include_croissant: Whether to include Croissant JSON-LD
            full_accountability: Whether to include full W3C PROV-O bundle
        
        Returns:
            URL of the pushed provenance
        """
        from huggingface_hub import HfApi, CommitOperationAdd
        
        api = HfApi(token=self.token)
        
        # Ensure repo exists
        api.create_repo(
            repo_id=repo_id,
            repo_type="dataset",
            private=private,
            exist_ok=True,
        )
        
        operations = []
        bundle = AccountabilityBundle(graph)
        
        # 1. CASCADE provenance JSON (native format)
        provenance_content = json.dumps(graph.to_dict(), indent=2, default=str)
        operations.append(CommitOperationAdd(
            path_in_repo=self.PROVENANCE_FILENAME,
            path_or_fileobj=provenance_content.encode("utf-8"),
        ))
        
        if full_accountability:
            # 2. W3C PROV-O JSON-LD (interoperable standard)
            prov_o_content = json.dumps(bundle.to_prov_o_jsonld(), indent=2, default=str)
            operations.append(CommitOperationAdd(
                path_in_repo=self.PROV_O_FILENAME,
                path_or_fileobj=prov_o_content.encode("utf-8"),
            ))
            
            # 3. W3C PROV-N notation (human readable)
            prov_n_content = bundle.to_prov_n()
            operations.append(CommitOperationAdd(
                path_in_repo=self.PROV_N_FILENAME,
                path_or_fileobj=prov_n_content.encode("utf-8"),
            ))
            
            # 4. Activity log (JSONL for easy grep/audit)
            activities = bundle.to_activity_log()
            activities_content = "\n".join(json.dumps(a, default=str) for a in activities)
            operations.append(CommitOperationAdd(
                path_in_repo=self.ACTIVITIES_FILENAME,
                path_or_fileobj=activities_content.encode("utf-8"),
            ))
            
            # 5. Agent attributions
            agents_content = json.dumps(bundle.to_agent_attributions(), indent=2, default=str)
            operations.append(CommitOperationAdd(
                path_in_repo=self.AGENTS_FILENAME,
                path_or_fileobj=agents_content.encode("utf-8"),
            ))
            
            # 6. Integrity manifest (for verification)
            integrity_content = json.dumps(bundle.to_integrity_manifest(), indent=2, default=str)
            operations.append(CommitOperationAdd(
                path_in_repo=self.INTEGRITY_FILENAME,
                path_or_fileobj=integrity_content.encode("utf-8"),
            ))
        
        # 7. Croissant JSON-LD (MLCommons standard)
        if include_croissant:
            exporter = CroissantExporter(graph)
            croissant_content = exporter.to_json(
                name=repo_id.split("/")[-1],
                url=f"https://huggingface.co/datasets/{repo_id}",
            )
            operations.append(CommitOperationAdd(
                path_in_repo=self.CROISSANT_FILENAME,
                path_or_fileobj=croissant_content.encode("utf-8"),
            ))
        
        # Commit all accountability artifacts
        api.create_commit(
            repo_id=repo_id,
            repo_type="dataset",
            operations=operations,
            commit_message=commit_message,
        )
        
        return f"https://huggingface.co/datasets/{repo_id}"
    
    def pull_provenance(self, repo_id: str) -> Optional[ProvenanceGraph]:
        """
        Pull provenance from HuggingFace Hub.
        
        Args:
            repo_id: HuggingFace repo ID
        
        Returns:
            ProvenanceGraph if found, None otherwise
        """
        from huggingface_hub import hf_hub_download
        
        try:
            # Download provenance file
            local_path = hf_hub_download(
                repo_id=repo_id,
                filename=self.PROVENANCE_FILENAME,
                repo_type="dataset",
                token=self.token,
            )
            
            with open(local_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            return ProvenanceGraph.from_dict(data)
            
        except Exception as e:
            print(f"Could not pull provenance from {repo_id}: {e}")
            return None
    
    def get_dataset_provenance_url(self, repo_id: str) -> str:
        """Get URL to provenance file in Hub."""
        return f"https://huggingface.co/datasets/{repo_id}/blob/main/{self.PROVENANCE_FILENAME}"
    
    def update_dataset_card(
        self,
        repo_id: str,
        graph: ProvenanceGraph,
    ) -> str:
        """
        Update dataset card with provenance summary.
        
        Adds/updates YAML front-matter with:
        - Lineage information
        - Root hash
        - Entity/activity counts
        
        Args:
            repo_id: HuggingFace repo ID
            graph: Provenance graph
        
        Returns:
            URL of the updated dataset
        """
        from huggingface_hub import HfApi, hf_hub_download
        
        api = HfApi(token=self.token)
        
        # Build provenance section for README
        provenance_section = self._build_readme_section(graph)
        
        # Get current README
        try:
            readme_path = hf_hub_download(
                repo_id=repo_id,
                filename="README.md",
                repo_type="dataset",
                token=self.token,
            )
            with open(readme_path, "r", encoding="utf-8") as f:
                current_readme = f.read()
        except:
            current_readme = f"# {repo_id.split('/')[-1]}\n\n"
        
        # Update or append provenance section
        marker_start = "<!-- CASCADE_PROVENANCE_START -->"
        marker_end = "<!-- CASCADE_PROVENANCE_END -->"
        
        if marker_start in current_readme:
            # Replace existing section
            import re
            pattern = re.escape(marker_start) + r".*?" + re.escape(marker_end)
            new_readme = re.sub(
                pattern,
                f"{marker_start}\n{provenance_section}\n{marker_end}",
                current_readme,
                flags=re.DOTALL,
            )
        else:
            # Append section
            new_readme = current_readme.rstrip() + f"\n\n{marker_start}\n{provenance_section}\n{marker_end}\n"
        
        # Push updated README
        api.upload_file(
            path_or_fileobj=new_readme.encode("utf-8"),
            path_in_repo="README.md",
            repo_id=repo_id,
            repo_type="dataset",
            commit_message="Update provenance in README",
        )
        
        return f"https://huggingface.co/datasets/{repo_id}"
    
    def _build_readme_section(self, graph: ProvenanceGraph) -> str:
        """Build provenance section for README."""
        stats = graph.stats
        bundle = AccountabilityBundle(graph)
        
        lines = [
            "## 🔗 Provenance & Accountability",
            "",
            "This dataset has CASCADE provenance tracking enabled with full W3C PROV-O compliance.",
            "",
            "### Integrity",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Root Hash | `{graph.root_hash[:16]}...` |",
            f"| Entities | {stats['entities']} |",
            f"| Activities | {stats['activities']} |",
            f"| Agents | {stats['agents']} |",
            f"| Relationships | {stats['relationships']} |",
            "",
        ]
        
        # Add lineage summary
        entities = graph.list_entities()
        if entities:
            lines.append("### Lineage")
            lines.append("")
            for entity in entities[:5]:  # Show first 5
                upstream = graph.get_lineage(entity.id, "upstream")
                if upstream:
                    lines.append(f"- **{entity.name}** derived from: {', '.join(upstream[:3])}")
                else:
                    lines.append(f"- **{entity.name}** (source)")
            if len(entities) > 5:
                lines.append(f"- ... and {len(entities) - 5} more entities")
            lines.append("")
        
        # Add activities summary
        activities = graph.list_activities()
        if activities:
            lines.append("### Activities")
            lines.append("")
            for activity in activities[:5]:
                duration = f" ({activity.duration:.2f}s)" if activity.duration else ""
                lines.append(f"- **{activity.name}** [{activity.activity_type.value}]{duration}")
            if len(activities) > 5:
                lines.append(f"- ... and {len(activities) - 5} more activities")
            lines.append("")
        
        # Add agents summary
        agents = graph.list_agents()
        if agents:
            lines.append("### Agents (Accountability)")
            lines.append("")
            for agent in agents[:5]:
                lines.append(f"- **{agent.name}** [{agent.agent_type.value}]")
            if len(agents) > 5:
                lines.append(f"- ... and {len(agents) - 5} more agents")
            lines.append("")
        
        # Accountability bundle files
        lines.extend([
            "### Accountability Bundle",
            "",
            "| File | Standard | Description |",
            "|------|----------|-------------|",
            f"| [{self.PROVENANCE_FILENAME}]({self.PROVENANCE_FILENAME}) | CASCADE | Native provenance format |",
            f"| [{self.PROV_O_FILENAME}]({self.PROV_O_FILENAME}) | W3C PROV-O | Interoperable JSON-LD |",
            f"| [{self.PROV_N_FILENAME}]({self.PROV_N_FILENAME}) | W3C PROV-N | Human-readable notation |",
            f"| [{self.ACTIVITIES_FILENAME}]({self.ACTIVITIES_FILENAME}) | JSONL | Activity audit log |",
            f"| [{self.AGENTS_FILENAME}]({self.AGENTS_FILENAME}) | JSON | Agent attributions |",
            f"| [{self.INTEGRITY_FILENAME}]({self.INTEGRITY_FILENAME}) | JSON | Hash verification manifest |",
            f"| [{self.CROISSANT_FILENAME}]({self.CROISSANT_FILENAME}) | MLCommons | Croissant metadata |",
            "",
        ])
        
        return "\n".join(lines)


def push_to_hub(
    graph: ProvenanceGraph,
    repo_id: str,
    token: str = None,
    private: bool = False,
) -> str:
    """
    Convenience function to push provenance to Hub.
    
    Args:
        graph: Provenance graph to push
        repo_id: HuggingFace repo ID
        token: HF token (optional)
        private: Whether repo should be private
    
    Returns:
        URL of the pushed provenance
    """
    hub = HubIntegration(token=token)
    return hub.push_provenance(graph, repo_id, private=private)


def pull_from_hub(repo_id: str, token: str = None) -> Optional[ProvenanceGraph]:
    """
    Convenience function to pull provenance from Hub.
    
    Args:
        repo_id: HuggingFace repo ID
        token: HF token (optional)
    
    Returns:
        ProvenanceGraph if found
    """
    hub = HubIntegration(token=token)
    return hub.pull_provenance(repo_id)
