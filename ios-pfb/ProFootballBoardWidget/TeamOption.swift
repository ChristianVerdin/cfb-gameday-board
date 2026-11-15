import AppIntents

/// The 32 clubs as text options; raw values are the abbreviations the board uses.
enum TeamOption: String, AppEnum, CaseIterable {
    case ARI, ATL, BAL, BUF, CAR, CHI, CIN, CLE, DAL, DEN, DET, GB, HOU, IND, JAX, KC
    case LAC, LAR, LV, MIA, MIN, NE, NO, NYG, NYJ, PHI, PIT, SEA, SF, TB, TEN, WSH

    static let typeDisplayRepresentation = TypeDisplayRepresentation(name: "Team")

    static let caseDisplayRepresentations: [TeamOption: DisplayRepresentation] = [
        .ARI: DisplayRepresentation(title: "Arizona Cardinals", subtitle: "ARI"),
        .ATL: DisplayRepresentation(title: "Atlanta Falcons", subtitle: "ATL"),
        .BAL: DisplayRepresentation(title: "Baltimore Ravens", subtitle: "BAL"),
        .BUF: DisplayRepresentation(title: "Buffalo Bills", subtitle: "BUF"),
        .CAR: DisplayRepresentation(title: "Carolina Panthers", subtitle: "CAR"),
        .CHI: DisplayRepresentation(title: "Chicago Bears", subtitle: "CHI"),
        .CIN: DisplayRepresentation(title: "Cincinnati Bengals", subtitle: "CIN"),
        .CLE: DisplayRepresentation(title: "Cleveland Browns", subtitle: "CLE"),
        .DAL: DisplayRepresentation(title: "Dallas Cowboys", subtitle: "DAL"),
        .DEN: DisplayRepresentation(title: "Denver Broncos", subtitle: "DEN"),
        .DET: DisplayRepresentation(title: "Detroit Lions", subtitle: "DET"),
        .GB: DisplayRepresentation(title: "Green Bay Packers", subtitle: "GB"),
        .HOU: DisplayRepresentation(title: "Houston Texans", subtitle: "HOU"),
        .IND: DisplayRepresentation(title: "Indianapolis Colts", subtitle: "IND"),
        .JAX: DisplayRepresentation(title: "Jacksonville Jaguars", subtitle: "JAX"),
        .KC: DisplayRepresentation(title: "Kansas City Chiefs", subtitle: "KC"),
        .LAC: DisplayRepresentation(title: "Los Angeles Chargers", subtitle: "LAC"),
        .LAR: DisplayRepresentation(title: "Los Angeles Rams", subtitle: "LAR"),
        .LV: DisplayRepresentation(title: "Las Vegas Raiders", subtitle: "LV"),
        .MIA: DisplayRepresentation(title: "Miami Dolphins", subtitle: "MIA"),
        .MIN: DisplayRepresentation(title: "Minnesota Vikings", subtitle: "MIN"),
        .NE: DisplayRepresentation(title: "New England Patriots", subtitle: "NE"),
        .NO: DisplayRepresentation(title: "New Orleans Saints", subtitle: "NO"),
        .NYG: DisplayRepresentation(title: "New York Giants", subtitle: "NYG"),
        .NYJ: DisplayRepresentation(title: "New York Jets", subtitle: "NYJ"),
        .PHI: DisplayRepresentation(title: "Philadelphia Eagles", subtitle: "PHI"),
        .PIT: DisplayRepresentation(title: "Pittsburgh Steelers", subtitle: "PIT"),
        .SEA: DisplayRepresentation(title: "Seattle Seahawks", subtitle: "SEA"),
        .SF: DisplayRepresentation(title: "San Francisco 49ers", subtitle: "SF"),
        .TB: DisplayRepresentation(title: "Tampa Bay Buccaneers", subtitle: "TB"),
        .TEN: DisplayRepresentation(title: "Tennessee Titans", subtitle: "TEN"),
        .WSH: DisplayRepresentation(title: "Washington Commanders", subtitle: "WSH"),
    ]

    var abbr: String { rawValue }
}
