#!/bin/bash
# SPPS Assistant — Interactive Lab Launcher

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# ── Verify the tool is available ─────────────────────────────────────────────
if ! command -v spps-assistant &>/dev/null; then
    echo -e "${RED}${BOLD}Error:${RESET} 'spps-assistant' command not found."
    echo ""
    echo "Please run the following once to install it:"
    echo "  python3 -m pip install spps-assistant"
    echo ""
    read -r -p "Press Enter to exit..."
    exit 1
fi

# ── Helpers ───────────────────────────────────────────────────────────────────
print_banner() {
    clear
    echo ""
    echo -e "${CYAN}${BOLD}  ╔════════════════════════════════════╗${RESET}"
    echo -e "${CYAN}${BOLD}  ║   SPPS Assistant v1.0 Launcher     ║${RESET}"
    echo -e "${CYAN}${BOLD}  ╚════════════════════════════════════╝${RESET}"
    echo ""
}

print_menu() {
    echo -e "  ${BOLD}What would you like to do?${RESET}"
    echo ""
    echo -e "  ${YELLOW}A.${RESET}  Download input templates     ${DIM}(sequence & reactants files)${RESET}"
    echo ""
    echo -e "  ${GREEN}1.${RESET}  Generate synthesis guide     ${DIM}(PDF + DOCX cycle guide)${RESET}"
    echo -e "  ${GREEN}2.${RESET}  Generate materials report    ${DIM}(XLSX shopping list)${RESET}"
    echo -e "  ${GREEN}3.${RESET}  Manage materials database    ${DIM}(add, list, import, export)${RESET}"
    echo -e "  ${GREEN}4.${RESET}  Configure synthesis defaults ${DIM}(activator, base, equivalents…)${RESET}"
    echo -e "  ${GREEN}5.${RESET}  Exit"
    echo ""
    echo -n "  Enter your choice [A, 0-5]: "
}

# Open a native macOS file-chooser dialog and return the selected POSIX path.
# All output goes to stdout; prompts that should be visible go to /dev/tty.
choose_file_dialog() {
    local prompt="${1:-Select a file:}"
    osascript -e "POSIX path of (choose file with prompt \"$prompt\")" 2>/dev/null || true
}

# Open a native macOS save-as dialog and return the chosen destination path.
choose_save_dialog() {
    local prompt="${1:-Save file as:}"
    osascript -e "POSIX path of (choose file name with prompt \"$prompt\")" 2>/dev/null || true
}

ask_output_dir() {
    local default="$HOME/Desktop/spps_output"
    echo "" >/dev/tty
    echo -n "  Output directory  [Enter = $default, 0 = back]: " >/dev/tty
    local dir
    read -r dir
    dir="${dir#"${dir%%[! ]*}"}"
    dir="${dir%"${dir##*[! ]}"}"
    dir="${dir//\\ / }"
    if [[ "$dir" == \'*\' ]]; then dir="${dir:1:${#dir}-2}"; fi
    if [ "$dir" = "0" ]; then printf '0'; return; fi
    if [ -z "$dir" ]; then dir="$default"; fi
    printf '%s' "$dir"
}

pause() {
    echo ""
    echo -n "  Press Enter to return to the menu..."
    read -r
}

# ── Option A: Download templates ──────────────────────────────────────────────
do_templates() {
    print_banner
    echo -e "  ${BOLD}${CYAN}A. Download Input Templates${RESET}"
    echo ""
    echo -e "  Templates explain the exact file format the tool expects."
    echo -e "  Fill them in, save, and use them as inputs for options 1 and 2."
    echo ""
    echo -e "  ${BOLD}Templates generated:${RESET}"
    echo -e "   ${GREEN}•${RESET} spps_sequences_template.fasta  — sequence input (FASTA format)"
    echo -e "   ${GREEN}•${RESET} spps_materials_template.csv    — information of your reactants (CSV)"
    echo -e "   ${GREEN}•${RESET} spps_materials_template.xlsx   — information of your reactants (Excel)"
    echo ""
    echo -e "  ${DIM}Press 0 at any time to return to the Home Screen.${RESET}"
    echo ""
    echo -n "  Enter a destination path, or press Enter to save to the Desktop: "
    read -r tdir
    tdir="${tdir#"${tdir%%[! ]*}"}"; tdir="${tdir%"${tdir##*[! ]}"}"; tdir="${tdir//\\ / }"
    if [[ "$tdir" == \'*\' ]]; then tdir="${tdir:1:${#tdir}-2}"; fi
    if [ -z "$tdir" ]; then tdir="$HOME/Desktop"; fi
    if [ "$tdir" = "0" ]; then return; fi

    echo ""
    echo -e "  ${GREEN}Generating templates in:${RESET} $tdir"
    echo ""
    spps-assistant template --output-dir "$tdir"
    local rc=$?
    echo ""
    if [ $rc -eq 0 ]; then
        echo -e "  ${GREEN}${BOLD}Done!${RESET} Open the folder to find your templates."
        open "$tdir" 2>/dev/null || true
    else
        echo -e "  ${RED}Something went wrong (exit code $rc).${RESET}"
    fi
    pause
}

# ── Option 1: Generate synthesis guide ───────────────────────────────────────
do_generate() {
    print_banner
    echo -e "  ${BOLD}${CYAN}1. Generate Synthesis Guide${RESET}"
    echo -e "  ${DIM}Produces a GMP cycle guide (PDF + DOCX) and peptide info sheet.${RESET}"
    echo ""
    echo -e "  ${BOLD}Step 1 of 3 — Select your sequence file${RESET}"
    echo -e "  ${DIM}A Finder window will open. Select your FASTA sequence file (.fasta).${RESET}"
    echo -e "  ${DIM}Press 0 at any time to return to the Home Screen.${RESET}"
    echo ""
    echo -n "  Press Enter to open the file picker, or 0 to go back: "
    local nav
    read -r nav
    if [ "$nav" = "0" ]; then return; fi

    local input_path
    input_path=$(choose_file_dialog "Select your FASTA sequence file (.fasta)")
    input_path="${input_path%$'\n'}"

    if [ -z "$input_path" ]; then
        echo ""
        echo -e "  ${YELLOW}No file selected — returning to the Home Screen.${RESET}"
        pause; return
    fi

    if [ ! -f "$input_path" ]; then
        echo ""
        echo -e "  ${RED}File not found: $input_path${RESET}"
        pause; return
    fi

    case "$input_path" in
        *.fasta|*.fa|*.FASTA|*.FA) ;;
        *)
            echo ""
            echo -e "  ${RED}Invalid file: expected a FASTA file (.fasta / .fa).${RESET}"
            pause; return
            ;;
    esac

    echo ""
    echo -e "  ${GREEN}Selected:${RESET} $input_path"
    echo ""
    echo -e "  ${BOLD}Step 2 of 3 — Reactants file (optional)${RESET}"
    echo -n "  Do you have a reactants file with MW values? [y/N, 0 = back]: "
    read -r has_mat
    if [ "$has_mat" = "0" ]; then return; fi
    local cmd=(spps-assistant generate --input "$input_path")
    if [[ "$has_mat" =~ ^[Yy] ]]; then
        echo ""
        echo -e "  ${DIM}A Finder window will open. Select your reactants file (.xlsx or .csv).${RESET}"
        echo -n "  Press Enter to open the file picker, or 0 to skip: "
        read -r _nav2
        if [ "$_nav2" != "0" ]; then
            local mat_path
            mat_path=$(choose_file_dialog "Select your reactants file (.xlsx or .csv)")
            mat_path="${mat_path%$'\n'}"
            if [ -f "$mat_path" ]; then
                echo -e "  ${GREEN}Selected:${RESET} $mat_path"
                cmd+=(--materials "$mat_path")
            else
                echo -e "  ${YELLOW}No reactants file selected — continuing without it.${RESET}"
            fi
        else
            echo -e "  ${YELLOW}Skipping reactants file — continuing without it.${RESET}"
        fi
    fi

    echo ""
    echo -e "  ${BOLD}Step 3 of 3 — Output directory${RESET}"
    local out_dir
    out_dir=$(ask_output_dir)
    if [ "$out_dir" = "0" ]; then return; fi
    cmd+=(--output "$out_dir")

    echo ""
    echo -e "  ${GREEN}Running…${RESET}"
    echo ""
    "${cmd[@]}"
    local rc=$?
    echo ""
    if [ $rc -eq 0 ]; then
        echo -e "  ${GREEN}${BOLD}Done!${RESET} Output files saved to:"
        echo -e "  ${CYAN}$out_dir${RESET}"
        open "$out_dir" 2>/dev/null || true
    else
        echo -e "  ${RED}Something went wrong (exit code $rc). Check the messages above.${RESET}"
    fi
    pause
}

# ── Option 2: Materials report ────────────────────────────────────────────────
do_materials() {
    print_banner
    echo -e "  ${BOLD}${CYAN}2. Generate Materials Report${RESET}"
    echo -e "  ${DIM}Produces an XLSX shopping list with masses and volumes for each reagent.${RESET}"
    echo ""
    echo -e "  ${BOLD}Step 1 of 3 — Select your sequence file${RESET}"
    echo -e "  ${DIM}A Finder window will open. Select your FASTA sequence file (.fasta).${RESET}"
    echo -e "  ${DIM}Press 0 at any time to return to the Home Screen.${RESET}"
    echo ""
    echo -n "  Press Enter to open the file picker, or 0 to go back: "
    local nav
    read -r nav
    if [ "$nav" = "0" ]; then return; fi

    local input_path
    input_path=$(choose_file_dialog "Select your FASTA sequence file (.fasta)")
    input_path="${input_path%$'\n'}"

    if [ -z "$input_path" ]; then
        echo ""
        echo -e "  ${YELLOW}No file selected — returning to the Home Screen.${RESET}"
        pause; return
    fi

    if [ ! -f "$input_path" ]; then
        echo ""
        echo -e "  ${RED}File not found: $input_path${RESET}"
        pause; return
    fi

    case "$input_path" in
        *.fasta|*.fa|*.FASTA|*.FA) ;;
        *)
            echo ""
            echo -e "  ${RED}Invalid file: expected a FASTA file (.fasta / .fa).${RESET}"
            pause; return
            ;;
    esac

    echo ""
    echo -e "  ${GREEN}Selected:${RESET} $input_path"
    echo ""
    echo -e "  ${BOLD}Step 2 of 3 — Reactants file (optional)${RESET}"
    echo -n "  Do you have a reactants file with MW values? [y/N, 0 = back]: "
    read -r has_mat
    if [ "$has_mat" = "0" ]; then return; fi
    local cmd=(spps-assistant materials --input "$input_path")
    if [[ "$has_mat" =~ ^[Yy] ]]; then
        echo ""
        echo -e "  ${DIM}A Finder window will open. Select your reactants file (.xlsx or .csv).${RESET}"
        echo -n "  Press Enter to open the file picker, or 0 to skip: "
        read -r _nav2
        if [ "$_nav2" != "0" ]; then
            local mat_path
            mat_path=$(choose_file_dialog "Select your reactants file (.xlsx or .csv)")
            mat_path="${mat_path%$'\n'}"
            if [ -f "$mat_path" ]; then
                echo -e "  ${GREEN}Selected:${RESET} $mat_path"
                cmd+=(--materials "$mat_path")
            else
                echo -e "  ${YELLOW}No reactants file selected — continuing without it.${RESET}"
            fi
        else
            echo -e "  ${YELLOW}Skipping reactants file — continuing without it.${RESET}"
        fi
    fi

    echo ""
    echo -e "  ${BOLD}Step 3 of 3 — Output directory${RESET}"
    local out_dir
    out_dir=$(ask_output_dir)
    if [ "$out_dir" = "0" ]; then return; fi
    cmd+=(--output "$out_dir")

    echo ""
    echo -e "  ${GREEN}Running…${RESET}"
    echo ""
    "${cmd[@]}"
    local rc=$?
    echo ""
    if [ $rc -eq 0 ]; then
        echo -e "  ${GREEN}${BOLD}Done!${RESET} Report saved to:"
        echo -e "  ${CYAN}$out_dir${RESET}"
        open "$out_dir" 2>/dev/null || true
    else
        echo -e "  ${RED}Something went wrong (exit code $rc).${RESET}"
    fi
    pause
}

# ── Option 3: Database management ────────────────────────────────────────────
do_database() {
    while true; do
        print_banner
        echo -e "  ${BOLD}${CYAN}3. Materials Database${RESET}"
        echo ""
        echo -e "  ${GREEN}1.${RESET}  List all entries in the database"
        echo -e "  ${GREEN}2.${RESET}  Add a new entry manually"
        echo -e "  ${GREEN}3.${RESET}  Export database to CSV"
        echo -e "  ${GREEN}4.${RESET}  Import materials from a CSV or XLSX file"
        echo -e "  ${GREEN}5.${RESET}  Back to main menu"
        echo -e "  ${GREEN}0.${RESET}  Back to Home Screen"
        echo ""
        echo -n "  Choice [0-5]: "
        read -r dchoice

        case "$dchoice" in
            1)
                echo ""
                spps-assistant db --list
                pause
                ;;
            2)
                echo ""
                echo -e "  ${DIM}Examples: C(Acm), K(Boc), R(Pbf), S(tBu), HBTU, DIEA${RESET}"
                echo -n "  Token to add: "
                read -r tok
                tok="${tok// /}"
                if [ -n "$tok" ]; then
                    spps-assistant db --add "$tok"
                fi
                pause
                ;;
            3)
                echo ""
                echo -e "  ${DIM}A Save dialog will open — choose the destination CSV file.${RESET}"
                local ep
                ep=$(choose_save_dialog "Save export CSV as...")
                ep="${ep%$'\n'}"
                if [ -n "$ep" ]; then
                    spps-assistant db --export "$ep"
                fi
                pause
                ;;
            4)
                echo ""
                echo -e "  ${DIM}A Finder window will open — select your CSV or XLSX file.${RESET}"
                local ip
                ip=$(choose_file_dialog "Select a CSV or XLSX materials file to import:")
                ip="${ip%$'\n'}"
                if [ -z "$ip" ]; then
                    echo -e "  ${YELLOW}No file selected.${RESET}"
                elif [ -f "$ip" ]; then
                    echo -e "  ${GREEN}Importing:${RESET} $ip"
                    spps-assistant db --import "$ip"
                else
                    echo -e "  ${RED}File not found: $ip${RESET}"
                fi
                pause
                ;;
            5|0) return ;;
            *) echo -e "  ${RED}Invalid choice.${RESET}"; sleep 1 ;;
        esac
    done
}

# ── Option 4: Configure defaults ──────────────────────────────────────────────
do_setup() {
    print_banner
    echo -e "  ${BOLD}${CYAN}4. Configure Synthesis Defaults${RESET}"
    echo -e "  ${DIM}Set your lab's default activator, base, reactant excess, vessel type, etc.${RESET}"
    echo -e "  ${DIM}These values are saved and pre-filled the next time you generate a guide.${RESET}"
    echo -e "  ${DIM}Press 0 to return to the Home Screen at any time.${RESET}"
    echo ""
    spps-assistant setup
    pause
}

# ── Main loop ─────────────────────────────────────────────────────────────────
while true; do
    print_banner
    print_menu
    read -r choice

    case "$choice" in
        A|a) do_templates ;;
        1)   do_generate  ;;
        2)   do_materials ;;
        3)   do_database  ;;
        4)   do_setup     ;;
        5)
            echo ""
            echo -e "  ${CYAN}Goodbye!${RESET}"
            echo ""
            exit 0
            ;;
        0)
            # "0" at the main menu is a no-op — already at Home Screen
            ;;
        *)
            echo ""
            echo -e "  ${RED}Invalid choice — please enter A or a number from 1 to 5.${RESET}"
            echo -e "  ${DIM}(Press 0 from any sub-menu to return to the Home Screen.)${RESET}"
            sleep 1
            ;;
    esac
done
