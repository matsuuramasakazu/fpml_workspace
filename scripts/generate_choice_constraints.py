import os
import re
from pathlib import Path
from lxml import etree

NS = {"xsd": "http://www.w3.org/2001/XMLSchema"}

def camel_to_snake(name: str) -> str:
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

def parse_substitution_groups(xsd_dir: Path):
    substitutions = {}
    for xsd_file in xsd_dir.glob("*.xsd"):
        try:
            tree = etree.parse(str(xsd_file))
            root = tree.getroot()
            # グローバルレベルの xsd:element で substitutionGroup 属性を持つものを探す
            for elem in root.findall("xsd:element[@substitutionGroup]", namespaces=NS):
                sub_grp = elem.get("substitutionGroup")
                sub_grp_name = sub_grp.split(":")[-1]
                elem_name = elem.get("name")
                
                sub_grp_snake = camel_to_snake(sub_grp_name)
                elem_snake = camel_to_snake(elem_name)
                
                if sub_grp_snake not in substitutions:
                    substitutions[sub_grp_snake] = []
                substitutions[sub_grp_snake].append(elem_snake)
        except Exception as e:
            print(f"Warning: Error parsing substitution groups in {xsd_file.name}: {e}")
    return substitutions

def parse_xsd_groups(xsd_dir: Path):
    groups = {}
    for xsd_file in xsd_dir.glob("*.xsd"):
        try:
            tree = etree.parse(str(xsd_file))
            root = tree.getroot()
            for group_el in root.findall(".//xsd:group[@name]", namespaces=NS):
                group_name = group_el.get("name")
                elem_names = []
                for elem in group_el.findall(".//xsd:element", namespaces=NS):
                    name = elem.get("name")
                    if name:
                        elem_names.append(camel_to_snake(name))
                    else:
                        ref = elem.get("ref")
                        if ref:
                            elem_names.append(camel_to_snake(ref.split(":")[-1]))
                groups[group_name] = elem_names
        except Exception as e:
            print(f"Warning: Error parsing groups in {xsd_file.name}: {e}")
    return groups

def expand_substitutions(option_fields: list, substitutions: dict) -> list:
    current_options = [[]]
    for field in option_fields:
        if field in substitutions:
            next_options = []
            for opt in current_options:
                for sub_val in substitutions[field]:
                    next_options.append(opt + [sub_val])
            current_options = next_options
        else:
            for opt in current_options:
                opt.append(field)
    return current_options

def parse_choice_constraints(xsd_dir: Path, groups: dict, substitutions: dict):
    constraints = {}
    for xsd_file in xsd_dir.glob("*.xsd"):
        try:
            tree = etree.parse(str(xsd_file))
            root = tree.getroot()
            
            for ct in root.findall(".//xsd:complexType[@name]", namespaces=NS):
                ct_name = ct.get("name")
                choices = ct.findall(".//xsd:choice", namespaces=NS)
                if not choices:
                    continue
                
                ct_constraints = []
                for choice in choices:
                    min_occurs = choice.get("minOccurs", "1")
                    choice_required = (min_occurs != "0")
                    
                    options = []
                    any_option_required = False
                    
                    for child in choice.getchildren():
                        if not isinstance(child.tag, str):
                            continue
                        tag = child.tag.split("}")[-1]
                        
                        child_min_occurs = child.get("minOccurs", "1")
                        child_required = (child_min_occurs != "0")
                        
                        option_fields = []
                        option_required = child_required
                        
                        if tag == "element":
                            name = child.get("name")
                            if name:
                                option_fields.append(camel_to_snake(name))
                            else:
                                ref = child.get("ref")
                                if ref:
                                    option_fields.append(camel_to_snake(ref.split(":")[-1]))
                        elif tag == "group":
                            ref = child.get("ref")
                            if ref:
                                ref_name = ref.split(":")[-1]
                                if ref_name in groups:
                                    option_fields.extend(groups[ref_name])
                        elif tag == "sequence":
                            seq_required = (child_min_occurs != "0")
                            has_seq_required_element = False
                            
                            for seq_child in child.findall(".//xsd:element", namespaces=NS):
                                name = seq_child.get("name")
                                seq_child_min = seq_child.get("minOccurs", "1")
                                if seq_child_min != "0":
                                    has_seq_required_element = True
                                
                                if name:
                                    option_fields.append(camel_to_snake(name))
                                else:
                                    ref = seq_child.get("ref")
                                    if ref:
                                        option_fields.append(camel_to_snake(ref.split(":")[-1]))
                                        
                            for seq_grp in child.findall(".//xsd:group", namespaces=NS):
                                ref = seq_grp.get("ref")
                                seq_grp_min = seq_grp.get("minOccurs", "1")
                                if seq_grp_min != "0":
                                    has_seq_required_element = True
                                if ref:
                                    ref_name = ref.split(":")[-1]
                                    if ref_name in groups:
                                        option_fields.extend(groups[ref_name])
                                        
                            option_required = seq_required and has_seq_required_element
                        
                        if option_fields:
                            # substitutionGroup 展開
                            expanded = expand_substitutions(option_fields, substitutions)
                            for opt_f in expanded:
                                seen = set()
                                unique = [f for f in opt_f if not (f in seen or seen.add(f))]
                                options.append(unique)
                            if option_required:
                                any_option_required = True
                                
                    required = choice_required and any_option_required
                    
                    if len(options) > 1:
                        ct_constraints.append({
                            "options": options,
                            "required": required
                        })
                        
                if ct_constraints:
                    constraints[ct_name] = ct_constraints
        except Exception as e:
            print(f"Warning: Error parsing complexTypes in {xsd_file.name}: {e}")
            
    return constraints

def write_constraints_file(output_path: Path, constraints: dict):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# This file is auto-generated by scripts/generate_choice_constraints.py.\n")
        f.write("# Do not edit manually.\n\n")
        f.write("CHOICE_CONSTRAINTS = {\n")
        
        for ct_name in sorted(constraints.keys()):
            f.write(f"    \"{ct_name}\": [\n")
            for c in constraints[ct_name]:
                f.write("        {\n")
                f.write("            \"options\": [\n")
                for opt in c["options"]:
                    f.write(f"                {opt},\n")
                f.write("            ],\n")
                f.write(f"            \"required\": {c['required']},\n")
                f.write("        },\n")
            f.write("    ],\n")
            
        f.write("}\n")

def main():
    workspace_root = Path(__file__).resolve().parent.parent
    xsd_dir = workspace_root / "confirmation"
    output_path = workspace_root / "src" / "validators" / "rules" / "choice_constraints.py"
    
    print("Parsing XSD substitution groups...")
    substitutions = parse_substitution_groups(xsd_dir)
    print(f"Found {len(substitutions)} substitution groups.")
    
    print("Parsing XSD groups...")
    groups = parse_xsd_groups(xsd_dir)
    print(f"Found {len(groups)} groups.")
    
    print("Parsing choice constraints...")
    constraints = parse_choice_constraints(xsd_dir, groups, substitutions)
    print(f"Found choice constraints for {len(constraints)} types.")
    
    print(f"Writing constraints to {output_path}...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_constraints_file(output_path, constraints)
    print("Done!")

if __name__ == "__main__":
    main()
